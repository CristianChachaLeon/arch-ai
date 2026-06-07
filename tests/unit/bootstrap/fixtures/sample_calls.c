#include <stdio.h>

void helper_function() {
    printf("helper\n");
}

void internal_caller() {
    helper_function();
}

void external_caller() {
    external_function();
}

void multi_caller() {
    helper_function();
    internal_caller();
    another_external();
}

static void static_func() {
    helper_function();
}
