from setuptools import setup, find_packages

setup(
	name='wvcfrs-parser',
	version='0.1-alpha',
	author='Austin B. Siford',
	author_email='austin.siford@gmail.com',
	packages=find_packages(),
	install_requires=open('requirements.txt').read().splitlines(),
	description='A tool to parse WVSoS\'s campaign finance disclosure PDFs into structured data for analysis.',
	long_description=open('README.md').read(),
	long_description_content_type='text/markdown',
	url='https://github.com/austindizzy/wvcfrs-parser',
	classifiers=[
		'License :: OSI Approved :: MIT License',
		'Programming Language :: Python :: 3',
		'Programming Language :: Python :: 3.12',
	],
)