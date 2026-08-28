SPHINXBUILD   = sphinx-build
SOURCEDIR     = source
BUILDDIR      = _build

.PHONY: html
html:
	$(SPHINXBUILD) -M html "$(SOURCEDIR)" "$(BUILDDIR)"

.PHONY: clean
clean:
	rm -rf $(BUILDDIR)/*
