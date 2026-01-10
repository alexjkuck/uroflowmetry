/*
 * LD20-2600B Flow Sensor Reader for ESP32
 * 
 * Connections:
 * SDA > GPIO 21, SCL > GPIO 22, VDD > 3.3V, GND > GND
 */

#include <Wire.h>

#define SENSOR_ADDRESS 0x08
#define FLOW_SCALE_FACTOR 20.0    // Convert raw value to ml/h
#define TEMP_SCALE_FACTOR 200.0   // Convert raw value to C

// Calculate CRC-8 checksum to verify data integrity
uint8_t calculateCRC(uint8_t data[], uint8_t len) {
  uint8_t crc = 0xFF;
  
  for (uint8_t i = 0; i < len; i++) {
    crc ^= data[i];
    for (uint8_t bit = 8; bit > 0; --bit) {
      if (crc & 0x80) {
        crc = (crc << 1) ^ 0x31;
      } else {
        crc = (crc << 1);
      }
    }
  }
  return crc;
}

// Send command to start continuous measurement
void startMeasurement() {
  Wire.beginTransmission(SENSOR_ADDRESS);
  Wire.write(0x36);  // Command byte 1
  Wire.write(0x08);  // Command byte 2
  Wire.endTransmission();
  delay(120);  // Sensor warm-up time
}

// Read 9 bytes from sensor: Flow(2) + CRC(1) + Temp(2) + CRC(1) + Flags(2) + CRC(1)
bool readMeasurement(int16_t &flowValue, int16_t &tempValue, uint16_t &flags) {
  Wire.requestFrom(SENSOR_ADDRESS, 9);
  
  if (Wire.available() < 9) return false;
  
  // Read flow rate (2 bytes + CRC)
  uint8_t flowData[2];
  flowData[0] = Wire.read();  // MSB (Most Significant Byte)
  flowData[1] = Wire.read();  // LSB (Least Significant Byte)
  uint8_t flowCRC = Wire.read();
  if (calculateCRC(flowData, 2) != flowCRC) return false;
  
  // Read temperature (2 bytes + CRC)
  uint8_t tempData[2];
  tempData[0] = Wire.read();  // MSB
  tempData[1] = Wire.read();  // LSB
  uint8_t tempCRC = Wire.read();
  if (calculateCRC(tempData, 2) != tempCRC) return false;
  
  // Read status flags (2 bytes + CRC)
  uint8_t flagData[2];
  flagData[0] = Wire.read();  // MSB
  flagData[1] = Wire.read();  // LSB
  uint8_t flagCRC = Wire.read();
  if (calculateCRC(flagData, 2) != flagCRC) return false;
  
  // Combine 2 bytes into 16-bit value: (MSB << 8) | LSB
  flowValue = (int16_t)((flowData[0] << 8) | flowData[1]);
  tempValue = (int16_t)((tempData[0] << 8) | tempData[1]);
  flags = (uint16_t)((flagData[0] << 8) | flagData[1]);
  
  return true;
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("LD20-2600B Flow Sensor");
  Serial.println("Flow | Temp | Air | HighFlow");
  
  Wire.begin();  // Initialize I2C
  Wire.setClock(400000);  // Set I2C speed to 400kHz
  delay(30);  // Wait for sensor power-up
  
  startMeasurement();
}

void loop() {
  int16_t rawFlow, rawTemp;
  uint16_t flags;
  
  if (readMeasurement(rawFlow, rawTemp, flags)) {
    
    // Convert raw values to physical units
    float flowRate = rawFlow / FLOW_SCALE_FACTOR;      // ml/h
    float temperature = rawTemp / TEMP_SCALE_FACTOR;   // C
    
    // Extract status flags using bitwise AND
    bool airInLine = flags & 0x0001;    // Bit 0: Air bubble detected
    bool highFlow = flags & 0x0002;     // Bit 1: Flow exceeds limit
    
    // Print results
    Serial.print(flowRate, 2);
    Serial.print(" ml/h | ");
    Serial.print(temperature, 2);
    Serial.print(" C | ");
    Serial.print("Air in the line? ");
    Serial.print(airInLine ? "YES" : "NO");
    Serial.print(" | ");
    Serial.print("High Flow? ");
    Serial.println(highFlow ? "YES" : "NO");
  }
  
  delay(1000);
}
