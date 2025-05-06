void expon(double x, double y, double *out) {
    // Hard-to-symbolically-execute function
    *out = (int)exp(sqrt(x * x + y * y)) % 10000;
}
