#!/usr/bin/python

import sys
sys.path.append("/mnt/flash/local/GitBundleToCloud")
import bundleToCloud

options = dict()
options["tmp"]                   = "/mnt/tmp"
options["awsBucket"]             = "gitolite_bundles"
options["awsStorageClass"]       = "REDUCED_REDUNDANCY"
options["symmetricKeyLabel"]     = "key0001"
options["symmetricKey"]          = "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"
options["baseDir"]               = "/mnt/flash/gitolite/repositories"
options["AWS_ACCESS_KEY_ID"]     = "xxxxxxxxxxxxxxxxxxxx"
options["AWS_SECRET_ACCESS_KEY"] = "yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy"
options["keepNBundles"]          = 2

bundleToCloud.bundleToCloud(options)


# Now check, and cancel, multi-part uploads
bundleToCloud.checkForFailedMultipartUploads(options)
