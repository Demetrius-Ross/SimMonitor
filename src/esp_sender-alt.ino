#include <esp_now.h>
#include <WiFi.h>

// Receiver ESP MAC Address
uint8_t receiverMAC[] = {0x78, 0xE3, 0x6D, 0xDF, 0x69, 0x7C}; //  main ESP MAC address

// Data structure to send
typedef struct {
  char message[32];
} Message;

Message myData;

void onSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
  Serial.print("Last Packet Send Status: ");
  Serial.println(status == ESP_NOW_SEND_SUCCESS ? "Success" : "Fail");
}

void setup() {
  Serial.begin(115200);

  // Initialize Wi-Fi
  WiFi.mode(WIFI_STA);

  // Initialize ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing ESP-NOW");
    return;
  }

  // Register send callback
  esp_now_register_send_cb(onSent);

  // Register peer
  esp_now_peer_info_t peerInfo;
  memcpy(peerInfo.peer_addr, receiverMAC, 6);
  peerInfo.channel = 0; // Default channel
  peerInfo.encrypt = false;

  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println("Failed to add peer");
    return;
  }
}

void loop() {
  // Prepare and send data
  strcpy(myData.message, "Hello ESP-NOW!");
  esp_err_t result = esp_now_send(receiverMAC, (uint8_t *)&myData, sizeof(myData));

  if (result == ESP_OK) {
    Serial.println("Message sent successfully");
  } else {
    Serial.println("Failed to send message");
  }

  delay(2000); // Wait 2 seconds before sending again
}
