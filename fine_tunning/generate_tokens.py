from constants import MAX_TOKENS_INPUT,MAX_TOKENS_OUTPUT#, PROMPT
from constants import PROMPT_ARTICULO,PROMPT_GENERAL,PROMPT_LIBRO,PROMPT_TESIS,PROMPT_OBJECTO_CONFERENCIA
from constants import SCHEMA_ARTICULO,SCHEMA_GENERAL,SCHEMA_LIBRO,SCHEMA_TESIS,SCHEMA_OBJECTO_CONFERENCIA
import json
from datasets import Dataset,DatasetDict
import torch


def input_text_schema( text, schema, example=["","",""]):
    schema = json.dumps(json.loads(schema), indent=4) # Limpia y formatea el JSON
    input_llm =  "<|input|>\n### Template:\n" +  schema + "\n"
    for i in example:
      if i != "":
          input_llm += "### Example:\n"+ json.dumps(json.loads(i), indent=4)+"\n" # Few shots examples
    
    input_llm +=  "### Text:\n"+text +"\n<|output|>\n"
    return input_llm


def input_text(text,prompt):
    return  f"{prompt} Document: {text}"

def get_prompt_by_type(type):
    if type == "Articulo":
        return PROMPT_ARTICULO
    if type == "Tesis":
        return PROMPT_TESIS
    if type == "Objeto de conferencia":
        return PROMPT_OBJECTO_CONFERENCIA
    return PROMPT_LIBRO

def get_schema_by_type(type):
    if type == "Articulo":
        return SCHEMA_ARTICULO
    if type == "Tesis":
        return SCHEMA_TESIS
    if type == "Objeto de conferencia":
        return SCHEMA_OBJECTO_CONFERENCIA
    return SCHEMA_LIBRO



def  get_general_dict(dict):
    items_to_add = {"dc.language" : "language","dc.title" : "title" ,"dc.title.subtitle" : "subtitle" , "sedici.creator.person" : "creator" ,
                    "sedici.rights.license" : "rights", "sedici.rights.uri" : "rightsurl","dc.date.issued" : "date",
                    "mods.originInfo.place" : "originPlaceInfo"}
    #"dc.identifier.uri": "dc.uri" ,"sedici.rights.uri":"sedici.uri","dc.subject.ford" : "subject", "sedici.relation.isRelatedWith":"isrelatedwith"
    return {k: v for k, v in dict.items() if k in items_to_add.values()}



# --------------------------------------------
# Genera el dataset con schema y ejemplos de entrenamiento
# --------------------------------------------

def add_schema_and_structure(dict_dataset):
    formatted_data = {}
    for step in dict_dataset.keys():
        step_data = []
        for item in dict_dataset[step]:  
            original_text = item["original_text"]
            # Paso General
            schema_type =get_schema_by_type(item["type"]) 
            output_text = json.dumps(get_general_dict(item)) # Metadatos comunes entre todos los tipos
            step_data.append({"input": input_text_schema(original_text,SCHEMA_GENERAL), "output": output_text})
            
            # Paso Específico
            final_dict = {k: v for k, v in item.items() if  k != "type" and k != "dc.type" and k != "original_text" and k != "keywords" and k != "dc.uri" and k != "sedici.uri" and k != "abstract" and k != "subject" and k != "isRelatedWith" and k != "isrelatedwith"}
            output_text = json.dumps(final_dict) # Metadatos específicos del tipo
            step_data.append({"input": input_text_schema(original_text,schema_type), "output": output_text})
        formatted_data[step] = step_data
    dataset_dict = {}
    for step, step_data in formatted_data.items():
      dataset_dict[step] = Dataset.from_list(step_data) # Une los dos pasos en un dataset
    return DatasetDict(dataset_dict)




def add_prompt_and_structure(dict_dataset):
    formatted_data = {}
    for step in dict_dataset.keys():
        step_data = []
        for item in dict_dataset[step]:
            original_text = item["original_text"]
            prompt_type =get_prompt_by_type(item["type"]) # Obtiene el prompt según el tipo de documento
            # Paso General
            output_text = json.dumps(get_general_dict(item)) # Metadatos comunes entre todos los tipos
            step_data.append({"input": input_text(original_text,PROMPT_GENERAL), "output": output_text})
            # Paso Específico
            final_dict = {k: v for k, v in item.items() if  k != "type" and k != "dc.type" and k != "original_text" and k != "keywords" and k != "dc.uri" and k != "sedici.uri" and k != "abstract" and k != "subject" and k != "isRelatedWith" and k != "isrelatedwith"}
            output_text = json.dumps(final_dict) # Metadatos específicos del tipo
            step_data.append({"input": input_text(original_text,prompt_type), "output": output_text})
        formatted_data[step] = step_data
    print(formatted_data["training"][0]["output"])
    print(formatted_data["training"][1]["output"])
    dataset_dict = {}
    for step, step_data in formatted_data.items():
      dataset_dict[step] = Dataset.from_list(step_data)
    return DatasetDict(dataset_dict)


def preprocess_function(examples,tokenizer,model_type="causal"):
    inputs = examples['input']
    targets = examples['output']
    model_inputs = tokenizer(inputs, max_length=MAX_TOKENS_INPUT, truncation=True, padding="max_length")
    labels = tokenizer(targets, max_length=MAX_TOKENS_OUTPUT, truncation=True, padding="max_length")
    if model_type == "causal":
        input_ids = torch.tensor(model_inputs["input_ids"])  # Convertir a tensor
        label_ids = torch.tensor(labels["input_ids"])  # Convertir a tensor
        attention_mask = torch.tensor(model_inputs["attention_mask"])  # Convertir a tensor
        # 1️⃣ Concatenamos input_ids con label_ids
        combined_input_ids = torch.cat([input_ids, label_ids], dim=-1)  # [1, 1536]

        # 2️⃣ Extendemos la attention_mask
        combined_attention_mask = torch.cat([attention_mask, torch.ones(label_ids.shape, dtype=torch.long)], dim=-1)
        # Aclaración: A pesar de que la extensión de la máscara pone todos los tokens en 1, 
        # internamente el modelo NO tiene en cuenta los tokens del output para generar la salida (para no "hacer trampa")
        # pero sí tiene en cuenta los tokens del output para calcular la pérdida.

        # 3️⃣ Creamos los labels con -100 en la parte de input
        labels_padded = combined_input_ids.clone()
        labels_padded[:, :input_ids.shape[1]] = -100  # Ignorar tokens de entrada en la pérdida
        # Asignamos los valores correctos
        model_inputs["input_ids"] = combined_input_ids
        model_inputs["attention_mask"] = combined_attention_mask
        model_inputs["labels"] = labels_padded   
    else:
        model_inputs["labels"] = labels["input_ids"]
    return model_inputs



def get_tokens(dict_dataset,tokenizer,type_of_model="prompt",model_type="causal"):
    if type_of_model == "prompt":
        datasets = add_prompt_and_structure(dict_dataset)
    else:
        datasets = add_schema_and_structure(dict_dataset)
    dataset = datasets.map(preprocess_function, batched=True, fn_kwargs={"tokenizer" : tokenizer,"model_type":model_type})
    print(f"len of labels : {len(dataset['training'][0]['labels'])}")
    print(f"len of input_ids : {len(dataset['training'][0]['input_ids'])}")
    print(f"len of attention_mask : {len(dataset['training'][0]['attention_mask'])}")
    return dataset


def read_data_json(json_filename,enc):
    with open(json_filename, 'r', encoding=enc) as file:
        return json.load(file)


