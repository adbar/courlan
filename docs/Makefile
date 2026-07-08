SPHINXBUILD   = sphinx-build
SOURCEDIR     = docs/source
BUILDDIR      = docs/_build

.PHONY: html
html:
	$(SPHINXBUILD) -M html "$(SOURCEDIR)" "$(BUILDDIR)/html"

.PHONY: clean
clean:
	rm -rf $(BUILDDIR)/*
