#include <esp_now.h>
#include <WiFi.h>

// Data structure to receive
typedef struct {
  char message[32]; // Buffer for up to 31 characters + null terminator
} Message;

Message incomingData;

// Callback function for ESP-NOW
void onDataRecv(const esp_now_recv_info_t *recv_info, const uint8_t *incomingData, int len) {

  // Check for valid data length
  if (len > sizeof(Message)) { // Compare to the size of the Message structure
    Serial.println("Error: Received data too long!");
    return; // Prevent buffer overflow
  }

  // Use a buffer large enough to handle the received data
  char receivedMessage[sizeof(Message)] = {0}; // Dynamically allocate based on structure size
  memcpy(receivedMessage, incomingData, len);
  receivedMessage[len] = '\0'; // Null-terminate the string

  // Log the received MAC address
  Serial.print("Sender MAC: ");
  for (int i = 0; i < 6; i++) {
    Serial.print(recv_info->src_addr[i], HEX);
    if (i < 5) Serial.print(":");
  }
  Serial.println();

  // Log the actual message received
  Serial.print("Message received: ");
  Serial.println(receivedMessage);

  // Forward the data to the Raspberry Pi
  Serial.println(receivedMessage); // Send the received message directly
}

void setup() {
  Serial.begin(115200); // Open serial communication with Raspberry Pi

  // Initialize Wi-Fi in station mode
  WiFi.mode(WIFI_STA);

  // Initialize ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing ESP-NOW");
    return;
  }

  // Register the receive callback
  esp_now_register_recv_cb(onDataRecv);

  Serial.println("Main ESP ready to forward messages.");
}

void loop() {
  // Nothing to do in the main loop, data is handled in the callback
}
