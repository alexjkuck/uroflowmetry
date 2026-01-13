
/*************************************************************************
TO-DOs

consider adding 0.1 uF capacitor between +Vsupply and GND and as close to the sensor board as possible
(this is to mitigate potential impact of noise from one sensor affecting the other)

*************************************************************************/





// Board: DOIT ESP32 DEVKIT V1
// Serial Speed: 115200 baud


#include <Arduino.h>

#define TRUE 1
#define FALSE 0

/*=========== Header for READING SENSIRION FLOW SENSOR ===========*/

//  CONNECTIONS
//   SDA > GPIO 21
//   SCL > GPIO 22
//   VDD > 3.3V
//   GND > GND


#include <Wire.h>

#define SENSOR_ADDRESS 0x08
#define FLOW_SCALE_FACTOR 20.0    // Convert raw value to ml/h
#define TEMP_SCALE_FACTOR 200.0   // Convert raw value to C


/*=========== Header for READING SCALE ===========*/
#include "soc/rtc.h"
#include "HX711.h"

const int LOADCELL_DOUT_PIN = 19;
const int LOADCELL_SCK_PIN = 18;

const float SLOPE_gPADC = -0.037512675;// (-0.039580797);
const float INTERCEPT_g = -20107.22597; // (-21368.76167);

float lp_raw=0.0;

HX711 scale;

/*=========== Header for SAMPLING CONTROL ===========*/

// ---- sampling ----
static const uint32_t SAMPLE_HZ = 10;
static const uint32_t SAMPLE_PERIOD_US = 1000000UL / SAMPLE_HZ;  // 100000 us
static uint32_t nextSampleUs = 0;



/*=========== FUNCTIONS READING SENSIRION FLOW SENSOR ===========*/

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


/*************************************************************************
 *************************************************************************
--- MAIN ---

*************************************************************************
*************************************************************************/

void setup() {
  // put your setup code here, to run once:

//---- General Setup ----
  Serial.begin(115200);

  //-- from HX711 (Scale Breakout Board)
  rtc_cpu_freq_config_t config;
  rtc_clk_cpu_freq_get_config(&config);
  rtc_clk_cpu_freq_mhz_to_config(RTC_XTAL_FREQ_40M, &config);
  rtc_clk_cpu_freq_set_config_fast(&config);

//---- Setup Flow Sensor Reading ----
Wire.begin();  // Initialize I2C
Wire.setClock(400000);  // Set I2C speed to 400kHz
delay(30);  // Wait for sensor power-up
  
startMeasurement();


//---- Setup Scale Reading ----

  scale.begin(LOADCELL_DOUT_PIN, LOADCELL_SCK_PIN);

 if (scale.is_ready()) 
  {
    scale.set_scale();    
      
  } 
  else {
    Serial.println("HX711 not found.");
  }
 

}

//------------- LOOP ----------------------------------

void loop() 
{
  uint32_t now;
 
  bool new_scalevalue;
  float mass_g;
 
  long reading;
  


  // Initialize scheduler on first pass

  now = micros();
  if (nextSampleUs == 0) 
    nextSampleUs = now + SAMPLE_PERIOD_US;

  // Run exactly at 10 Hz
  if ((int32_t)(now - nextSampleUs) >= 0) 
  {
    nextSampleUs += SAMPLE_PERIOD_US;  // prevents drift  
    
    // -------- Read SCALE (HX711 @ 10 Hz) --------
    new_scalevalue = false;
    mass_g = 999.9f;
  
// Wait a little for the HX711 to become ready (10Hz => new sample every 100ms)
    // Give it up to 20ms so we usually catch the fresh sample even with small phase offset.
    if (scale.wait_ready_timeout(20)) 
    {
      new_scalevalue = true;
      reading = scale.read();

      
      mass_g = SLOPE_gPADC * (float)reading + INTERCEPT_g;
      
      
    }

// -------- Read FLOW (I2C) --------
    int16_t rawFlow = 0, rawTemp = 0;
    uint16_t flags = 0;
    bool new_flowvalue = false;

    float flowRate = 999.9f;   // ml/h
    uint8_t airInLine = 9;
    uint8_t highFlow  = 9;

    if (readMeasurement(rawFlow, rawTemp, flags)) 
    {
      new_flowvalue = true;
      flowRate = rawFlow / FLOW_SCALE_FACTOR;
      airInLine = (flags & 0x0001) ? 1 : 0;
      highFlow  = (flags & 0x0002) ? 1 : 0;
    }

// -------- Print ONE line per 10Hz tick --------
    // Format: mass_g;flowRate;air;high
    // (If a read failed, you’ll see 999.9 / 9s)

  uint32_t t_us = micros();   // timestamp for this sample tick

  Serial.print(t_us);
  Serial.print(",");

  Serial.print(new_scalevalue ? mass_g : 999.9f, 2);
  Serial.print(",");
  Serial.print(new_flowvalue ? flowRate : 999.9f, 2);
  Serial.print(",");
  Serial.print(airInLine);
  Serial.print(",");
  Serial.println(highFlow);
}

/*
  ---------------------------------------
  //-- flow variables
  int16_t rawFlow, rawTemp;
  uint16_t flags;
  bool new_flowvalue;

  float flowRate;    // ml/h
  float temperature; // C
  bool airInLine;    // Bit 0: Air bubble detected
  bool highFlow ;    // Bit 1: Flow exceeds limit
  
  //-- scale variables 
  float mass_g;
  float massLP_g;
  #define ALPHA 0.99
  bool new_scalevalue;

  //--- reading the flow sensor ---
  new_flowvalue = FALSE;
  if (readMeasurement(rawFlow, rawTemp, flags)) {
    new_flowvalue = TRUE;    
    // Convert raw values to physical units
    flowRate = rawFlow / FLOW_SCALE_FACTOR;      // ml/h
    temperature = rawTemp / TEMP_SCALE_FACTOR;   // C
    
    // Extract status flags using bitwise AND
    airInLine = flags & 0x0001;    // Bit 0: Air bubble detected
    highFlow = flags & 0x0002;     // Bit 1: Flow exceeds limit
    
  }


  //--- reading the scale ---
  new_scalevalue = FALSE;
  if (scale.is_ready()) 
  {
    
    new_scalevalue = TRUE;
    long reading = scale.read();
    lp_raw = ALPHA * lp_raw + (1.0-ALPHA)*(float) reading;
    mass_g = SLOPE_gPADC * (float) reading + INTERCEPT_g;
    massLP_g = SLOPE_gPADC * lp_raw + INTERCEPT_g;
  
    if(abs((int) mass_g- (int) massLP_g)>100)
      lp_raw =reading;

    
//    Serial.print(reading);
//    Serial.print("\t");
//    Serial.println(lp_raw);


  } 
 
//----- print results

//if(new_scalevalue)
  if(TRUE)
  {
    Serial.print(mass_g,2);
    Serial.print(";");
    //Serial.print(massLP_g);
  }
  else
  {
    Serial.print(999.9,2);
    Serial.print(";");
 //   Serial.println(" ");
  }

  if(new_flowvalue)
  {
    // Print results
    Serial.print(flowRate, 2);
    Serial.print(";");   
    Serial.print(airInLine ? 1 : 0);
    Serial.print(";");
    Serial.println(highFlow ? 1 : 0);
  }
  else
  {
    Serial.print(999.9, 2);
    Serial.print(";");
    Serial.print(9);
    Serial.print(";");
    Serial.println(9);
  }
*/
}

