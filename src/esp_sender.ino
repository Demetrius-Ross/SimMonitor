#include <WiFi.h> // Use <ESP8266WiFi.h> for ESP8266
#include <esp_now.h>

uint8_t mainESPAddress[] = {0x24, 0x6F, 0x28, 0x1A, 0x7D, 0xA4}; // Replace with main ESP MAC address

void setup() {
  Serial.begin(115200);
  
  // Initialize Wi-Fi in station mode
  WiFi.mode(WIFI_STA);
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing ESP-NOW");
    return;
  }
  
  // Register peer
  esp_now_peer_info_t peerInfo;
  memcpy(peerInfo.peer_addr, mainESPAddress, 6);
  peerInfo.channel = 0; // Use the same channel as the main ESP
  peerInfo.encrypt = false;
  
  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println("Failed to add peer");
    return;
  }
}

void loop() {
  // Example status message
  const char* message = "Red ON";
  esp_err_t result = esp_now_send(mainESPAddress, (uint8_t *)message, strlen(message));

  if (result == ESP_OK) {
    Serial.println("Message sent successfully");
  } else {
    Serial.println("Failed to send message");
  }
  
  delay(2000); // Adjust based on your needs
}
