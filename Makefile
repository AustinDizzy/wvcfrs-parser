.PHONY: install clean

# Install project dependencies
install:
	pip3 install -r requirements.txt

# Clean up pyc files and __pycache__ directories
clean:
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -exec rm -rf {} +