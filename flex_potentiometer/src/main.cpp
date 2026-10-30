#include <Arduino.h>

// Definer den analoge pinnen som sensoren er koblet til
const int FLEX_PIN = A0; 

// Spenningen som driver kretsen (endre til 3.3 hvis du bruker ESP32/NodeMCU/Teensy)
const float VCC = 5.0; 

// Verdien på den faste motstanden du koblet til GND (i ohm)
const float R_DIV = 10000.0; 

// KALIBRERING: Disse verdiene bør du justere basert på hva du ser i Serial Monitor
const float R_FLAT = 25000.0;  // Typisk motstand når sensoren er helt flat (~25kΩ)
const float R_BENT = 65000.0;  // Typisk motstand når sensoren er bøyd 90 grader (~65kΩ)

void setup() {
    // Start den serielle kommunikasjonen for å vise data på PC-en
    Serial.begin(9600);
    
    // Konfigurer den analoge pinnen som inngang
    pinMode(FLEX_PIN, INPUT);
}

void loop() {
    // 1. Les den rå analoge verdien (0 til 1023)
    int analogADC = analogRead(FLEX_PIN);
    
    // 2. Beregn spenningen på A0-pinnen
    float flexV = analogADC * VCC / 1023.0;
    
    // 3. Beregn den faktiske motstanden til Flex-sensoren basert på spenningsdeler-formelen
    float flexR = R_DIV * (VCC / flexV - 1.0);
    
    // 4. Estimer bøjevinkelen (0 til 90 grader) ved å mappe motstanden mot kalibreringsverdiene
    // constrain sørger for at vinkelen holder seg mellom 0 og 90 grader selv ved ekstrem bøy
    float angle = map(flexR, R_FLAT, R_BENT, 0.0, 90.0);
    angle = constrain(angle, 0.0, 90.0);
    
    // 5. Skriv ut resultatene til Serial Monitor
    Serial.print("Rå ADC: ");
    Serial.print(analogADC);
    Serial.print("  |  Motstand: ");
    Serial.print(flexR / 1000.0); // Viser i kΩ
    Serial.print(" kOhm  |  Bøjevinkel: ");
    Serial.print(angle, 1); // 1 desimal
    Serial.println(" grader");
    
    // Vent 200 millisekunder før neste avlesning
    delay(200);
}
