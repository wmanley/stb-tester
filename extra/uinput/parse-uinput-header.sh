uinput_h=$1

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
	from linux_input import *
	import ctypes
	
	EOF

(
	cat <<-EOF
		#include <stdio.h>
		#include <linux/uinput.h>

		int main(int argc, char *argv[])
		{
		EOF

	grep _IO "$uinput_h" | awk '{ print "    printf(\"%s = %i\\n\", \"" $2 "\", (int)" $2 ");" }'
	grep -v -e '(' -e ')' "$uinput_h" \
	  | awk '/#define/ { if (NF > 2) { print "    printf(\"%s = %i\\n\", \"" $2 "\", (int)" $2 ");" }}'

	cat <<-EOF
		    return 0;
		}
		EOF
) | interpret_c

cat <<-EOF
	
	class uinput_user_dev(ctypes.Structure):
	    _fields_ = [
	        ('name', ctypes.c_char * UINPUT_MAX_NAME_SIZE),
	        ('id', input_id),
	        ('ff_effects_max', ctypes.c_uint32),
	        ('absmax', ctypes.c_int32 * ABS_CNT),
	        ('absmin', ctypes.c_int32 * ABS_CNT),
	        ('absfuzz', ctypes.c_int32 * ABS_CNT),
	        ('absflat', ctypes.c_int32 * ABS_CNT),
	    ]
	EOF
