import paho.mqtt.client as mqtt
import json
from edit_dist import PhonemicMagic

def repaired_from_candidates(candidates):
    repaired = ""
    for candidate in candidates:
        if len(candidate) > 1:
            repaired += candidate[1][2]
        else:
            repaired += candidate[0]
        repaired += " "
    return repaired

def on_connect(client, userdata, flags, rc):
    client.subscribe("agent/asr")

def on_message(client, userdata, msg):
    # Load asr message into python object 
    obj = json.loads(msg.payload.decode("utf-8")) 
    if obj["data"]["is_final"]:
        text = obj["data"]["text"]
        candidates = phonemic_helper.process_utterance(text)
        repaired_text = repaired_from_candidates(candidates)
        
        # Published repaired asr message 
        obj_repaired = obj.copy()#{"header":obj["header"], "msg":obj["msg"], "data":{"text":text, "repaired_text":repaired_text}}
        obj_repaired["data"]["repaired_text"] = repaired_text
        client.publish("agent/asr/repaired", json.dumps(obj_repaired))


phonemic_helper = PhonemicMagic("cmu_feature_key.csv", "cmudict-0.7b.txt","stb_files/CELEXEnglish.fea.stb" ,"domain_words.csv" )

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect("127.0.0.1", 5556, 60)
client.loop_forever()
