GitBundleToCloud
================

Bundle all Git repos in a directory tree and upload, with optional encryption, to cloud storage for offsite backup.



Version
-------
0.0.1

Purpose
-------
Take all Git repos in a given directory, bundle them, optionally encrypt some, and upload to offsite "cloud" storage.
The decision to upload is taken only if the local repositiory is newer than the remote backup.

Caveats
-------
* This currently only works with AWS/S3. More/other options will be added in the future.
* AWS/S3 multi-part uploads are not supported yet. Bundles pushed to S3 are limited to about 5GB.

Example Repository Structure
----------------------------
I use this with gitolite. My gitolite structure looks like this:

    ~gitolite/repositories/
        gitolite-admin.git
        encrypted/
            Repo-A.git
            Repo-B.git
            SomeOtherDirectory/
                Repo-C.git
                Repo-D.git
                Repo-E.git
            private/
                Repo-E.git
                Repo-F.git
            public/
                Repo-G.git

The directory named ```encrypted``` is special. If it exists, repos in that directory will go through
encryption (after bundle, before upload). The other directories are not significant and are just an
artifact of my gitolite user/permission organization.

You can nest in subdirectores, they will be handled appropriately when pushed offsite.

Running
-------
Use your own python program to specify your AWS credentials, and encryption keys. For example:

    #!/usr/bin/python

    import sys
    sys.path.append("/mnt/flash/local/GitBundleToAWS")
    import bundleToS3

    options = dict()
    options["tmp"]                   = "/mnt/tmp"
    options["awsBucket"]             = "gitolite_bundles"
    options["symmetricKeyLabel"]     = "key0001"
    options["symmetricKey"]          = "################################"
    options["baseDir"]               = "/mnt/flash/NAS/gitolite/repositories"
    options["AWS_ACCESS_KEY_ID"]     = "123456789890abcedfea"
    options["AWS_SECRET_ACCESS_KEY"] = "asdf;lkjasdlkfjaslkdjfa;lskjdfalksjdfjkk"
    options["keepNBundles"]          = 4

    bundleToS3.bundleToS3(options)

Options
-------
Required Options:
* baseDir, The top-directory containing your Git repos.
* awsBucket, Name of the AWS bucket to store to. Do not prefix with "s:///".
* symmetricKeyLabel, A label used in the remote bundle name to identify what key was used to perform the encryption.
* symmetricKey, Actual symmetric key as passed to gpg for the encryption.
* ```AWS_ACCESS_KEY_ID```, See your AWS console for this.
* ```AWS_SECRET_ACCESS_KEY```, See your AWS console for this.
Optional:
* tmp, The directory to use for temporary files
* keepNBundles, How many bundles to keep in the remote storage
* awsStorageClass, STANDARD or REDUCED

Notes
-----
Do not lose your chosen "symmetricKey". I recommend recording it (KeePassX, etc.) along with the "symmetricKeyLabel".

TODO
====
Presented in order of importance:

* Done: Remove temporary files when done.
* Done: Add option for AWS reduced redundancy.
* AWS - Handle Multipart uploads (https://gist.github.com/fabiant7t/924094)
* AWS - Validate Multipart uploads.
* Add in support for Google Cloud Storage
* Validate gpg.
* Move away from subprocess.call() and do as much inline/stdin/stdout as possible.
* Check to make sure "git", "gpg", and other required programs/libraries are installed.
* Install as a python module.
