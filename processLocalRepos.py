#!/usr/bin/python

import bundleToS3

options = dict()
options["tmp"]                = "/mnt/tmp"
options["awsBucket"]          = "gitolite_bundles"
options["symmetricKeyLabel"] = "key0001"
options["symmetricKey"]      = "################################"
options["baseDir"]           = "/mnt/flash/NAS/gitolite/repositories"

bundleToS3.bundleToS3(options)

