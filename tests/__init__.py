# Mitigate the risk of random ResourceWarning unrelated to this package
# It happened on Travis CI with Pypy 3.5-5.10.1 and unittest2py3k 0.5.1
__import__('gc').collect()
