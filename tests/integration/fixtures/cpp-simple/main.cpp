#include "lib.hpp"
#include <iostream>

int counter = 0;

int main() {
    auto msg = greet("world");
    std::cout << msg << std::endl;
    return 0;
}

void increment() {
    counter++;
}
