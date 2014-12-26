"""
Bundle Git repos and push up to AWS.
"""
import sys
import os
import re
import time
import subprocess
import hashlib
try:
    import boto
except:
    sys.exit("Could not import boto - try adding the \"python-boto\" package\n")

import multipartUpload

def verifyAwsOptions(options):
    """ Verify the provided AWS access values 
    These options can come from the options dictionary, or from the environment """

    for e in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"):
        if e not in options:
            if e in os.environ:
                options[e] = os.environ[e]

def verifyOptions(options):
    """ Verify existence of required options. Provide sane values for optional arguments. """
    success = True

    # These are the options that must be present
    required = set();
    required.add("awsBucket")
    required.add("symmetricKeyLabel")
    required.add("symmetricKey")
    required.add("baseDir")
    required.add("AWS_ACCESS_KEY_ID")
    required.add("AWS_SECRET_ACCESS_KEY")

    # Bring over the AWS options iff they only exist in the environment
    verifyAwsOptions(options)

    # Be helpful if a required option is not found
    for check in required:
        if check not in options:
            print("\"{0}\" Needs to be defined in the options.\n".format(check))
            success = False

    # These are optional, if it doesn't exist, a sane value will be provided
    if "tmp" not in options:
        options["tmp"] = "/tmp"
    if "keepNBundles" not in options:
        options["keepNBundles"] = 4
    if "awsStorageClass" not in options:
        options["awsStorageClass"] = "STANDARD"

    return success

class Repository:
    def __init__(self, _options, _pathToRepo):
        self.options = _options #: Dictonary of validated options

        timeString = "{0}".format(int(time.time()))
        self.repoPath        = _pathToRepo #: Full path to the repo directory
        self.baseName        = _pathToRepo[len(self.options["baseDir"])+1:] #: Just the repo name
        self.baseTimeName    = self.baseName + "." + timeString #: Repo name with a timestamp
        self.flatName        = re.sub("/", "_", self.baseTimeName); #: replace directory components with '_'
        self.pathLocalBundle = "{0}/{1}.bundle".format(self.options["tmp"], self.flatName) #: temp file for the local git bundle
        self.tmpFiles = list()
        if re.match("encrypted/", self.baseName):
            self.pathLocalBundle    += "." + self.options["symmetricKeyLabel"];
            self.pathLocalEncrypted  = self.pathLocalBundle + ".gpg" #: Local encrypted bundle filename
            self.pathLocalFile       = self.pathLocalEncrypted
            self.pathRemoteFile      = "{0}.bundle.{1}.gpg".format(self.baseTimeName, self.options["symmetricKeyLabel"]) #: Remote name
            self.pathRemoteSha1sum   = self.baseTimeName + ".bundle.gpg.sha1sum"
            self.tmpFiles.append(self.pathLocalEncrypted)
        else:
            self.pathLocalEncrypted = None
            self.pathLocalFile      = self.pathLocalBundle
            self.pathRemoteFile     = self.baseTimeName + ".bundle"
            self.pathRemoteSha1sum  = self.baseTimeName + ".bundle.sha1sum"

        self.pathLocalSha1sum    = self.pathLocalFile + ".sha1sum"
        self.tmpFiles.append(self.pathLocalBundle)
        self.tmpFiles.append(self.pathLocalSha1sum)

    def __del__(self):
        pass

    def getName(self):
        return self.baseName

    def deleteTempFiles(self):
        """ Run through and delete any temporary files """
        for f in self.tmpFiles:
            os.unlink(f)

    def dumpValues(self):
        print("{0}".format(self.baseName))
        print(" BaseTimeName   = {0}".format(self.baseTimeName))
        pass

    def createBundle(self):
        """ Create the bundle of the Git repo """
        print(" Creating the bundle")
        os.chdir(self.repoPath)
        args = list()
        args.append("git")
        args.append("bundle")
        args.append("create")
        args.append(self.pathLocalBundle)
        args.append("--all")
        subprocess.call(args)
        pass

    def createSha1sum(self):
        """ Create a sha1sum of the Git bundle """
        print(" Creating the independent SHA1SUM")
        import hashlib
        BLOCKSIZE = 65536
        hasher = hashlib.sha1()
        with open(self.pathLocalFile, 'rb') as afile:
            buf = afile.read(BLOCKSIZE)
            while len(buf) > 0:
                hasher.update(buf)
                buf = afile.read(BLOCKSIZE)
        s = open(self.pathLocalSha1sum, "w")
        s.write("{0}  {1}\n".format(hasher.hexdigest(), os.path.basename(self.baseName)))
        print("  {0}".format(hasher.hexdigest()))
        pass

    def _simpleUpload(self, s3Bucket):
        """ Non multi-part upload. """
        bucketKey               = boto.s3.key.Key(s3Bucket)
        bucketKey.key           = self.pathRemoteFile
        bucketKey.storage_class = self.options["awsStorageClass"]
        bucketKey.set_contents_from_filename(self.pathLocalFile)
        pass

    def _multipartUpload(self, s3Connection):
        """ Multi-part upload. """
        rr = False
        if self.options["awsStorageClass"] == "REDUCED_REDUNDANCY":
            rr = True

        multipartUpload.upload(s3Connection,
                self.options["awsBucket"],
                self.options["AWS_ACCESS_KEY_ID"],
                self.options["AWS_SECRET_ACCESS_KEY"],
                self.pathLocalFile,
                self.pathRemoteFile,
                reduced_redundancy=rr)

    def upload(self, s3Connection, s3Bucket):
        """ Upload the bundle to offsite storage. """

        if True:
            # if < a size, simple upload, else, multipart
            if os.path.getsize(self.pathLocalFile) < 50*1024*1024:
                print(" Uploading the bundle (simple)")
                self._simpleUpload(s3Bucket)
            else:
                print(" Uploading the bundle (multi-part)")
                # TODO: use "try/except"
                self._multipartUpload(s3Connection)

            print(" Uploading the SHA1SUM file")
            bucketKey        = boto.s3.key.Key(s3Bucket)
            bucketKey.key    = self.pathRemoteSha1sum
            bucketKey.set_contents_from_filename(self.pathLocalSha1sum)

    def createEncryption(self):
        """ Upload the bundle to offsite storage.
        This is done iff encryption is specified. """
        if self.pathLocalEncrypted != None:
            print(" Creating the encrypted bundle")
            args = list()
            args.append("gpg")
            args.append("--symmetric")
            args.append("--compress-algo=none")
            args.append("--cipher-algo=AES256")
            args.append("--passphrase")
            args.append(self.options["symmetricKey"])
            args.append(self.pathLocalBundle)
            subprocess.call(args)
        else:
            print(" Skipping the encrypted bundle")

    def isRemoteStale(self, bucket):
        """ Check the remote timestamp and compare to files in the local repo """
        localMtime  = self.getYoungestLocalMtime()
        remoteMtime = self.getYoungestRemoteMtime(bucket) # GMT
        if localMtime < remoteMtime:
            return False
        else:
            return True

    def getYoungestRemoteMtime(self, bucket):
        """ Find the timestamp of the remote bundle """
        # Walk all items in the bucket
        # select out just those that match our current repo
        # check for the youngest
        maxMtime = 0
        for candidate in bucket.list(self.baseName):
            if re.search(".sha1sum", candidate.name):
                continue
            # pull out the timestamp - 1387314043
            m = re.search("\.(\d\d\d\d\d\d\d\d\d\d)\.", candidate.name)
            if m:
                if int(m.group(1)) > maxMtime:
                    maxMtime = int(m.group(1))
        if maxMtime == 0:
            # Nothing out there, so use an absurd past time
            maxMtime = time.mktime((1985, 03, 04, 0, 0, 0, 0, 0, 0))
#       print("{0} - Youngest remote".format(maxMtime))
        return maxMtime

    def getYoungestLocalMtime(self):
        """ Find the mtime of the youngest file in a local bundle """
        maxMtime = 0
        name = "none"
        for root, dirs, files in os.walk(self.repoPath):
            for f in files:
                # Ignore the file if it is named "config", gitolite seems to like to touch it
                if f == 'config':
                    continue
                mtime = os.stat(os.path.join(root, f)).st_mtime
                if mtime > maxMtime:
                    maxMtime = mtime
                    name = os.path.join(root, f)
#       print("{1} - Youngest local at {0}".format(name, int(maxMtime)))
        return maxMtime

    def purgeStaleBundles(self, bucket):
        """ Remove old remote bundles off the "stack" """
        print(" Purging old entries")

        candidates = list()
        for candidate in bucket.list(self.baseName):
            candidates.append(candidate.name)

        candidates = sorted(candidates)
        nFilesToKeep = self.options["keepNBundles"]*2

        for candidate in candidates[:-nFilesToKeep]:
            bucket.delete_key(candidate)
            print("  {0}".format(candidate))

def getAllGitRepos(options):
    """ Create a list of Repositries for local repos. """
    candidates = list()
    for root, dirs, files in os.walk(options["baseDir"]):
        for directory in dirs:
            if directory.endswith(".git"):
                r = Repository(options, os.path.join(root, directory))
                candidates.append(r)
    return candidates

def bundleToCloud(options):
    """ Starts the bundling process. """
    if False == verifyOptions(options):
        sys.exit()

    s3Connection = boto.connect_s3(options["AWS_ACCESS_KEY_ID"], options["AWS_SECRET_ACCESS_KEY"])
    s3Bucket     = s3Connection.get_bucket(options["awsBucket"])

    # search options["baseDir"] looking for bare git repos
    repositories = getAllGitRepos(options)

    for repository in repositories:
        if True == repository.isRemoteStale(s3Bucket):
            print("##################################")
            repository.dumpValues()
#           m = re.match("encrypted/", repository.getName())
#           if m:
#               print(" Skipping")
#               continue
            print(" Performing backup")
            repository.createBundle()
            repository.createEncryption()
            repository.createSha1sum()
            repository.upload(s3Connection, s3Bucket)
            repository.purgeStaleBundles(s3Bucket)
            repository.deleteTempFiles()
