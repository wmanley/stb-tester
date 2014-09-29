#!/bin/bash

#
# Old layout is:
#
#     $tag/$date_$time/...
#
# New nested layout is:
#
#     $node/$date/$time/...
#
# With tag recorded in a JSON file.

outdir=/var/lib/stbt/new-results

if [ "$1" = "-s" ]; then
    MV="ln -s"
    shift
else
    MV="cp -r"
fi

for tag in "$@";
do
    for d in $tag/20;
    do
        time="${d##*_}";
        s=${time##*.}
        h=${time%%.*}
        m=${time%%.$s}
        m=${m##$h.}
        day="${d%_*}";
        mkdir -p "$outdir/$day"
        $MV "$PWD/$tag/$d" "$outdir/$day/$h$m$s";
        printf '{"tag": "%s"}' "$(basename "$tag")" >"$outdir/$day/$h$m$s/tag.json"
    done
done
