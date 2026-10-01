PYTHON ?= python3
NODE ?= $(if $(BROLL_NODE),$(BROLL_NODE),node)

.PHONY: check package install-dry-run
check:
	$(PYTHON) scripts/validate_package.py
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py'
	$(NODE) --test tests/*.test.js

package:
	$(PYTHON) scripts/package.py

install-dry-run:
	$(PYTHON) scripts/install_skill.py --project . --host both --dry-run
