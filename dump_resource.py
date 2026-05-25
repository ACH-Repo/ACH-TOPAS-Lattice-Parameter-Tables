"""Regenerate the embedded resource blobs in cell_param_tables.py.

Reads resource.htm, extracts:
  - the space-group -> (formatted_html, crystal_system) lookup dict
  - the column template (resource HTML minus the lookup table and trailing
    stray <p> tags)

Encodes each as gzip+base64, formats as chunked Python literals, and replaces
the content between the marker lines

    # === EMBEDDED RESOURCE DATA ...
    ...
    # === END EMBEDDED RESOURCE DATA ===

in cell_param_tables.py in-place.

Usage:
    python dump_resource.py [path/to/resource.htm] [path/to/cell_param_tables.py]
"""

import sys
import os
import json
import gzip
import base64
import copy
import textwrap
from bs4 import BeautifulSoup


HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_RESOURCE = os.path.join(HERE, 'resource.htm')
DEFAULT_SCRIPT = os.path.join(HERE, 'cell_param_tables.py')

START_MARKER = '# === EMBEDDED RESOURCE DATA'
END_MARKER = '# === END EMBEDDED RESOURCE DATA ==='


def build_space2cryst(soup):

	'''Build the space-group lookup dict from the last table in the soup.

	Values are (formatted_html_string, crystal_system).'''

	out = {}
	table = soup.find_all('table')[-1]
	for tr in table.find_all('tr')[1:]:
		tds = tr.find_all('td')
		if len(tds) < 3:
			continue
		keys = tds[0].text.strip().split(';')
		formatted = ''.join(str(c) for c in tds[1].p.contents)
		system = tds[2].text.strip()
		for k in keys:
			out[k.lower().strip()] = [formatted, system]
	return out


def build_template_html(soup):

	'''Return the resource HTML with the space-group lookup table and trailing
	stray <p> tags removed.'''

	tpl = copy.copy(soup)
	tpl.find_all('table')[-1].decompose()
	for p in tpl.find_all('p')[-2:]:
		p.decompose()
	return str(tpl)


def encode_blob(text):

	'''Encode `text` as a gzip+base64 ASCII string.'''

	g = gzip.compress(text.encode('utf-8'), compresslevel=9)
	return base64.b64encode(g).decode('ascii')


def format_literal(name, b64, width=76):

	'''Format a long base64 string as a Python tuple of 76-char string literals
	(which Python implicitly concatenates).'''

	lines = textwrap.wrap(b64, width=width)
	body = '\n'.join("    '%s'" % ln for ln in lines)
	return "%s = (\n%s\n)" % (name, body)


def render_block(sg_lit, tpl_lit):

	'''Render the full embedded-data block, including marker lines.'''

	header = (
		'# === EMBEDDED RESOURCE DATA — generated from resource.htm; '
		'regenerate with dump_resource.py ===\n'
		'# _SG_B64   : gzip+base64 of JSON dict { sg_key_lower: '
		'[formatted_html_str, crystal_system] }\n'
		'# _TPL_B64  : gzip+base64 of the resource HTML with the space-group '
		'lookup table and trailing\n'
		'#             stray <p> tags already stripped — ready to use as '
		'the column template.'
	)
	return '%s\n%s\n\n%s\n%s' % (header, sg_lit, tpl_lit, END_MARKER)


def replace_between_markers(script_text, new_block):

	'''Locate the embedded-data block in `script_text` and replace it.'''

	start = script_text.find(START_MARKER)
	if start == -1:
		raise RuntimeError('start marker not found: %r' % START_MARKER)
	end = script_text.find(END_MARKER, start)
	if end == -1:
		raise RuntimeError('end marker not found: %r' % END_MARKER)
	end += len(END_MARKER)
	return script_text[:start] + new_block + script_text[end:]


def main(argv):
	resource_path = argv[1] if len(argv) > 1 else DEFAULT_RESOURCE
	script_path = argv[2] if len(argv) > 2 else DEFAULT_SCRIPT

	if not os.path.isfile(resource_path):
		sys.exit('resource not found: %s' % resource_path)
	if not os.path.isfile(script_path):
		sys.exit('script not found: %s' % script_path)

	with open(resource_path, 'rb') as f:
		soup = BeautifulSoup(f, 'html.parser')

	sg_dict = build_space2cryst(soup)
	tpl_html = build_template_html(soup)

	sg_json = json.dumps(sg_dict, separators=(',', ':'))
	sg_lit = format_literal('_SG_B64', encode_blob(sg_json))
	tpl_lit = format_literal('_TPL_B64', encode_blob(tpl_html))

	new_block = render_block(sg_lit, tpl_lit)

	with open(script_path, 'r', encoding='utf-8') as f:
		script_text = f.read()
	patched = replace_between_markers(script_text, new_block)
	with open(script_path, 'w', encoding='utf-8') as f:
		f.write(patched)

	print('Updated %s' % script_path)
	print('  space-group entries: %d' % len(sg_dict))
	print('  template html chars: %d' % len(tpl_html))


if __name__ == '__main__':
	main(sys.argv)
