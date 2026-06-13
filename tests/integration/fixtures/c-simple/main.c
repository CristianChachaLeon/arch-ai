#include "lib.h"
#include <stdio.h>

int counter = 0;

int main(void) {
    int result = greet("world");
    printf("Result: %d\n", result);
    return 0;
}

void increment(void) {
    counter++;
}
