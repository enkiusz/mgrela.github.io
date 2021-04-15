#!/bin/sh

emacs --batch -l publish.el --eval '(org-publish "magical-index")'
(cd _site; git commit -a -m 'rebuild'; git push)
