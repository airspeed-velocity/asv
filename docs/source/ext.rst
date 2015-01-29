Plugins
=======

``asv`` has some optional features that may be enabled by adding them
to the ``plugins`` list in ``asv.conf.json``.  For example, to enable
the ``asv.ext.ccache`` plugin, add the following to your
``asv.conf.json``::

   "plugins": ["asv.ext.ccache"]

asv.ext.ccache
--------------

Normally, when using ``asv`` with ``ccache`` it is not very effective
because the location of the build products is randomized.  This plugin
makes ``ccache`` more amenable to that, resulting in more cache hits
and faster compilation.
