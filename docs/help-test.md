# Help test your projector

Every test so far was done on one VisionMaster Pro2. AWOL Link is also documented for the VisionMaster Pro, Max, Plus2 and Plus, but nobody has tried this integration on them yet. If you own one of these, or a Pro2 with different firmware, your results help everyone with the same model.

Everything below is done in Home Assistant. No computer tools, scripts or command lines needed. Do as many tests as you like, even one helps.

## Before you start

1. Install the integration and add your projector (see the [README](../README.md#installation)).
2. Note your projector model and firmware. Both are shown on the device page under *Device info*.

## Report your results

Open a [model test report](https://github.com/The-HBA/ha-valerion/issues/new?template=model_report.yml) and write what you saw. "Works", "error message: ..." or "nothing happened" is enough. Please attach the diagnostics download (device page > three dots > Download diagnostics). It does not contain your IP address, MAC address or security code.

## Open questions

| Model | What we want to know most |
| --- | --- |
| VisionMaster Max | Do the lens shift, zoom and focus menu buttons work? Does Wake-on-LAN switch it on from standby? Is *Film* motion enhancement available? |
| VisionMaster Pro | Everything: nothing has been tested yet |
| VisionMaster Plus2, Plus | Everything: nothing has been tested yet |
| VisionMaster Pro2 | Aspect ratio in HDR10+ and HLG. Results on firmware other than V02.01.00E.Q0718 |

## Level 1: easy (a few minutes, no settings changed)

1. **Device info.** Open the projector's device page. Are model and firmware correct?
2. **Lens menus.** Press *Lens shift menu*, *Zoom menu* and *Focus menu* (under Configuration). Does the menu appear on the projector, or does Home Assistant show an error? A refused menu button hides itself, so note which one before you press.
3. **Navigation buttons.** Press Up, Down, OK, Return and Home. Does the projector react?
4. **Sensors.** Play something and look at *Video signal*, *HDR format* and the diagnostic sensors (audio format, color depth, fans, temperatures). Do the values look right?
5. **Diagnostics.** Download diagnostics while a video is playing and attach it to your report.

## Level 2: medium (needs a video playing)

1. **Standby.** Switch the projector off from Home Assistant. Check the *AWOL Link status* sensor after 1 minute and after 10 minutes: *answering*, *silent* or *unreachable*?
2. **Power on.** Enter the projector's MAC address (Settings > Devices & services > Valerion > gear button). Switch the projector off, wait 10 minutes, then switch it on from the media player. Did it come on? Try again after a night in standby.
3. **Picture modes.** Open the *Picture mode* list while playing SDR, HDR10, HDR10+, HLG and Dolby Vision. Write down the list for each format.
4. **Settings per format.** With each format playing, try to change *Gamma*, *Dynamic tone mapping*, *Color temperature*, *Enhanced black level*, *Laser level* and *Aspect ratio*. Note which ones work and which show an error. Set them back afterwards.
5. **Motion enhancement.** Try every option, including *Film*. Which ones are refused?
6. **Volume.** Change the volume from the media player. Does the projector's own volume change? Tell us if you use the projector speakers or an external receiver or soundbar.

## Level 3: advanced (Developer tools)

1. **Raw commands.** Open Developer tools > Actions, choose *Valerion: Send raw command* and enter a command, for example `%1POWR ?`. Press *Perform action*; the reply appears below. Useful commands:
   - `%3LSMN ?`, `%3ZMMN ?`, `%3FCMN ?` open the lens shift, zoom and focus menus (same as the buttons, but the reply shows the exact error code).
   - `%3MOTN 2` tries *Film* motion enhancement.
   - `%3PICL ?` lists the picture modes for the current signal.
2. **Full power off.** Send `%1POWR 2`. On the Pro2 this is refused. If your projector switches fully off, try switching it on from the media player and tell us whether it came back. Only try this when you can reach the IR remote.
3. **Debug log of a wake.** On the Valerion integration page choose *Enable debug logging*. Switch the projector on from deep standby (after a night). Then choose *Disable debug logging*: the log downloads. Attach it to your report.

Thank you for helping.
