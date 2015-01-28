/**
 * @file
 *
 * @date Jun 25, 2013
 * @author: Anton Bondarev
 */

#include <stdio.h>

extern void print_pybuild_pretty(void);

int main(void) {
	print_pybuild_pretty();
	printf("\n%s from Pybuild v%s!\n", GREETING, MYBUILD_VERSION);
	return 0;
}
