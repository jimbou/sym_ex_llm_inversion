#include <stdio.h>
#include <math.h>
#include <stdlib.h>

void expon(double x, double y, double *out) {
    // Hard-to-symbolically-execute function
    *out = (int)exp(sqrt(x * x + y * y)) % 10000;
}

int main() {
    double x = 0.0;
    double y = 1.0;
    double z = x*y +2;
    x=x+y;
    double result = 0.0;

    expon(x, y, &result);

    result=result + 1.0;
    printf("Result: %f\n", result);
    return 0;
}
