# Home Assistant integration of the KEF LS 50 Wireless
Supported: KEF LS50 Wireless (Requires up to date firmware)

Untested: KEF LSX

## Credit 
This project is based on code from **Gronis** (https://github.com/Gronis/pykef) and investigations of **chimpy** (wireshark god).


## Features supported
- Get and set volume
- Mute and unmute
- Get and set source input
- Turn off speaker
- Turn on speaker (via HA service call)

## Discussion
See [home assistant thread](https://community.home-assistant.io/t/kef-ls50-wireless/)


### Use in Home Assistant
1. Create folder in your home assistant main folder:
```bash
mkdir custom_components/media_player
```
2. Copy pykef.py and kefwireless.py into that folder. This will make the custom component kefwireless available to Home Assistant: 
```bash
cp pykef.py custom_components/media_player
cp kefwireless.py custom_components/media_player
```
3. Add component to Home Assistant by adding to configuration.yaml and restart HA:
```bash
media_player:
   - platform: kefwireless
     host: 192.168.x.x # change to the IP of you speaker, no autodetection yet
     name: MyLS50W # optional, the name you want to see in Home Assistant
     turn_on_service: switch.turn_on # optional, place a HA service to call in here: domain.service 
     turn_on_service_data: '{"entity_id": "switch.some_switch"}' # optional, place the service data in here. Must be in quotation marks ('). Must be one line   
```

##Limitations
- LS50 speakers take about 20 seconds to boot. Thus, after turning them on please be patient. Turning them on via HA is not possible. 


## License
MIT License

## Authors
- Robin Grönberg
- Bastian Beggel
- chimpy (wireshark god)
