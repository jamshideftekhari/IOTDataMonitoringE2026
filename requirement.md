R1: simulation a weather station semsor which send data to a central API. snensor parameters and API IP address can be changed from a configuration file. 
R2: i want to save measurements as timeseries data in mogodb atlas cluster which I have with following connection string save in compass-connections.json. and measure document is following:
{
  "timestamp": ISODate("2025-08-19T12:00:00Z"),
  "metaField": {
    "sensorId": "A1234",
    "location": {
      "city": "New York",
      "state": "NY"
    }
  },
  "temperature": 25.4,
  "humidity": 48.2,
  "pressure": 1012.5,
  "windSpeed": 5.2,
  "windDirection": "NW"
}
