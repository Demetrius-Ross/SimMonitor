#include <WiFi.h> // Include the Wi-Fi library

void setup() {
  Serial.begin(115200);
  
  // Initialize Wi-Fi
  WiFi.mode(WIFI_STA); // Set Wi-Fi to station mode
  delay(100);          // Small delay for Wi-Fi initialization
  
  // Get and print the MAC address
  Serial.print("MAC Address: ");
  Serial.println(WiFi.macAddress());
}

void loop() {
  // Do nothing
}