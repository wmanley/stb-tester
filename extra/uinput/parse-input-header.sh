#!/bin/bash -e

input_h=$1

interpret_c()
{
	tmpexe="$(mktemp ./temp-exec.XXXXXX)"
	tmpc="$(mktemp ./temp-c.XXXXXX)"
	(
		cat <<-EOF
			#include <stdio.h>
			#include <linux/input.h>
		
			int main(int argc, char *argv[]) {
			EOF
		cat
		cat 
		cat <<-EOF
				return 0;
			}
			EOF
	) >"$tmpc"
	gcc -Wall -xc "$tmpc" -o "$tmpexe" 1>&2 &&
	"$tmpexe" &&
	rm "$tmpc" "$tmpexe"
}

cat <<-EOF
	#
	# This file was generated from $input_h using
	# parse-input-header.sh, a part of stb-tester[1].  Do not edit.
	#
	# [1]: http://stb-tester.com
	#
	
	import ctypes
	import sysconfig
	
	key = {}
	EOF

cat "$input_h" \
  | gawk --lint  '
    /#define[[:space:]]+\w+_(CNT|MAX)[[:space:]]+/ { print "    printf(\"%s = %lli\\n\", \"" $2 "\", (long long int)" $2 ");"; next; }
    /#define[[:space:]]+(KEY|BTN)_\w+[[:space:]]+/ { print "    printf(\"key[\\\"%s\\\"] = %lli\\n\", \"" $2 "\", (long long int)" $2 ");"; next; }
    /#define[[:space:]]+\w+[[:space:]]+/ { if (NF > 2) { print "    printf(\"%s = %lli\\n\", \"" $2 "\", (long long int)" $2 ");" }}' \
  | interpret_c

cat <<-EOF
	
	_ttsize = sysconfig.get_config_var('SIZEOF_TIME_T')
	time_t = { 4: ctypes.c_int32, 8: ctypes.c_int64 }[_ttsize]
	class timeval(ctypes.Structure):
	    _fields_ = [
	        ('tv_sec', time_t),
	        ('tv_usec', ctypes.c_uint32)
	    ]
	
	EOF


cat $input_h \
 | sed -E 's/__u([0-9]+)/ctypes.c_uint\1/g' \
 | sed -E 's/__s([0-9]+)/ctypes.c_int\1/g' \
 | sed 's/;//g' \
 | grep -v -e "union" \
 | awk '/^struct/ { print "class " $2 "(ctypes.Structure):\n    _fields_ = [";
                    in_struct=1 }
        /^\tstruct/ { if (in_struct == 1) { print "        (\"" $3 "\", " $2 "),"  }; next }
        /^\t[a-zA-Z]/ { if (in_struct == 1) { print "        (\"" $2 "\", " $1 "),"  } }
        /^}/ { print "    ]\n";
               in_struct=0 }'
