#!/usr/bin/python
# coding=utf-8


import argparse
import subprocess
import sys
import tempfile
from textwrap import dedent
from tempfile import NamedTemporaryFile
from shutil import rmtree
import os
from collections import namedtuple

import ImageFont

from gi.repository import Pango

example_text = u"""The quick brown fox jumped over the lazy dog.
THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG.
A Stitch In Time Saves Nine.
My Telephone Number is +4470123456789
My email address is example@example.com (but not really!)
She said "Is Abdul's TV bright?" and I said: "Not really; I'm just trying to use
punctuation.  This would be easy: with code, where I can use {curly brackets} and
mathematical symbols like:

7 + 3 = 10
2 * 4 = 8
12-3 = 9 and is 25% of 36.
PEP8 says this_is_an_identifier.
Hex looks like 0x45ABC642
2^5 = 32 but costs £1.54 or $2.31

In Python comments are like # you can use
Refer to, paths, in your home directory with, ~/my/path.txt
<img/> tags are useful in HTML but in shell | can be even better
You can escape charactors with \ like \\n for newline.

I like fish & chips.
"""

langdata = '/home/william-manley/Projects/tesseract-ocr/training/langdata'

Font = namedtuple('Font', 'id name filename base flags')

class FontFlags(object):
    ITALIC = 1 << 0
    BOLD = 1 << 1
    FIXED = 1 << 2
    SERIF = 1 << 3
    FRAKTUR = 1 << 4

def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("font_file", nargs='+',
                        help="Filename of a OpenType font")
    parser.add_argument(
        "--lang", default="eng",
        help="Three letter ISO 639-2 language code.  e.g. \"eng\"")
    parser.add_argument("--exp", default=0, help="Not sure yet...")
    parser.add_argument("--shape-clustering", action="store_true",
                        help="Enable this option for Indic languages")
    args = parser.parse_args(argv[1:])

    fonts = []

    for font in args.font_file:
        family, style = ImageFont.truetype(font).getname()

        if style == 'Regular':
            name = family
        else:
            name = family + " " + style

        fid = "".join(name.split())
        flags = 0
        if "italic" in style.lower():
            flags |= FontFlags.ITALIC
        if "bold" in style.lower():
            flags |= FontFlags.BOLD
        #TODO: Work out if it's fixed width or has serifs
        fonts.append(Font(id=fid,
                          name=name,
                          filename=os.path.abspath(font),
                          base='%s.%s.exp%i' % (args.lang, fid, args.exp),
                          flags=flags))

    outfile = os.path.abspath("%s.traineddata" % args.lang)

    tmpdir = tempfile.mkdtemp()
    try:
        os.chdir(tmpdir)
        for font in fonts:
            # Generate box files
            with NamedTemporaryFile() as text:
                text.write(example_text.encode('utf-8'))
                text.flush()
                subprocess.check_call([
                    'text2image',
                    '--text=%s' % text.name,
                    '--outputbase=%s' % font.base,
                    '--font=%s' % font.name,
                    '--fonts_dir=%s' % os.path.dirname(font.filename),
                    '--degrade_image=false',
                    '--xsize=1280',
                    '--ysize=720',
                    '--ptsize=6'
                    ])

            subprocess.check_call([
                'tesseract',
                '%s.tif' % font.base,
                font.base,
                'box.train.stderr'])

        subprocess.check_call(
            ['unicharset_extractor'] +
            ['%s.box' % font.base for font in fonts])

        subprocess.check_call([
            'set_unicharset_properties',
            '-U', 'unicharset', '-O', 'unicharset', '--script_dir=%s' % langdata])

        with open('font_properties', 'w') as f:
            for font in fonts:
                f.write("%s %i %i %i %i %i\n" % (
                    font.id,
                    font.flags & FontFlags.ITALIC and 1,
                    font.flags & FontFlags.BOLD and 1,
                    font.flags & FontFlags.FIXED and 1,
                    font.flags & FontFlags.SERIF and 1,
                    font.flags & FontFlags.FRAKTUR and 1))

        if args.shape_clustering:
            subprocess.check_call([
                'shapeclustering',
                '-F', 'font_properties',
                '-U', 'unicharset'] +
                ['%s.tr' % f.base for f in fonts])

        subprocess.check_call([
            'mftraining',
            '-F', 'font_properties',
            '-U', 'unicharset',
            '-O', '%s.unicharset' % args.lang] +
            ['%s.tr' % f.base for f in fonts])
        assert os.path.exists('%s.unicharset' % args.lang)

        subprocess.check_call(['cntraining'] + ['%s.tr' % f.base for f in fonts])

        os.rename('inttemp', '%s.inttemp' % args.lang)
        os.rename('pffmtable', '%s.pffmtable' % args.lang)
        os.rename('shapetable', '%s.shapetable' % args.lang)
        os.rename('font_properties', '%s.font_properties' % args.lang)
        os.rename('normproto', '%s.normproto' % args.lang)

        subprocess.check_call(['combine_tessdata', '%s.' % args.lang])
        os.rename('%s.traineddata' % args.lang, outfile)
    finally:
        print tmpdir
#        rmtree(tmpdir)

if __name__ == '__main__':
    sys.exit(main(sys.argv))
