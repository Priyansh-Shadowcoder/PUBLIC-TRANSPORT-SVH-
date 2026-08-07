#include <iostream>
#include <cmath>
#include <string>

int main(int argc, char* argv[]) {

    if (argc < 5) {
        std::cerr << "Error: Missing coordinates." << std::endl;
        return 1;
    }
    double src_lat = std::stod(argv[1]);
    double src_lon = std::stod(argv[2]);
    double dest_lat = std::stod(argv[3]);
    double dest_lon = std::stod(argv[4]);

    double dLat = dest_lat - src_lat;
    double dLon = dest_lon - src_lon;
    double distance = std::sqrt(dLat * dLat + dLon * dLon) * 111.0; 

    std::cout << distance << std::endl;
    
    return 0;
}