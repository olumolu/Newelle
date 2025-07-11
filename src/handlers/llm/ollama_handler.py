import threading 
import json 
import requests 
from subprocess import Popen 
from typing import Any, Callable
import time

from ..handler import ErrorSeverity

from .llm import LLMHandler
from ...utility.system import can_escape_sandbox, get_spawn_command
from ...utility.media import extract_image
from ...utility import get_streaming_extra_setting
from ...handlers import ExtraSettings

class OllamaHandler(LLMHandler):
    key = "ollama"
    default_models = (("llama3.1:8b", "llama3.1:8b"), )
    model_library = []
    # Url where to get the available models info
    library_url = "https://nyarchlinux.moe/available_models.json"
    # List of models to be included in the library by default
    listed_models = ["qwen3:4b", "qwen3:8b", "deepseek-r1:8b", "qwen3:14b", "llama3.2-vision:11b", "deepseek-r1:1.5b", "deepseek-r1:7b", "deepseek-r1:14b", "llama3.2:3b", "llama3.1:8b", "qwq:32b", "qwen2.5:1.5b", "qwen2.5:3b", "qwen2.5:7b", "qwen2.5:14b", "gemma2:2b", "gemma2:9b", "qwen2.5-coder:3b", "qwen2.5-coder:7b", "qwen2.5-coder:14b", "llama3.3:70b", "phi4:14b"]

    def __init__(self, settings, path):
        super().__init__(settings, path)
        models = self.get_setting("models", False)
        self.downloading = {}
        if self.get_setting("model-library", False) is not None:
            self.model_library = self.get_setting("model-library", False)
        if models is None or len(models) == 0:
            self.models = self.default_models
            lr = self.get_setting("last_request", False)
            if lr is None or time.time() - lr > 3600:
                self.set_setting("last_request", time.time())
                threading.Thread(target=self.get_models, args=()).start()
        else:
            self.models = json.loads(models)
        if self.get_setting("models-info", False) is not None:
            self.models_info = self.get_setting("models-info", False)
        else:
            self.models_info = {}
            threading.Thread(target=self.get_models_infomation, args=()).start()

    def get_models_list(self):
        return self.models

    def get_models_infomation(self):
        """Get information about models on ollama.com"""
        if self.is_installed(): 
            try:
                info = requests.get(self.library_url).json()
                self.set_setting("models-info", info)
                print(info)
                self.models_info = info
                self.add_library_information()
                self.settings_update()
            except Exception as e:
                print("Error getting ollama get_models_infomation" + str(e))
   
    def get_info_for_library(self, model):
        """Get information about a model in the library

        Args:
            model (): name of the model 

        Returns:
           dict - information to be added to the library 
        """
        if ":" in model:
            name = model.split(":")[0]
            tag = model.split(":")[1]
            if name in self.models_info:
                title = " ".join([name, tag])
                if self.models_info[name]["description"] is None:
                    description = ""
                else:
                    description = str(self.models_info[name]["description"])
                    description += "\nSize: " + "".join([t[1] for t in self.models_info[name]["tags"] if t[0] == tag])
                return {"key": model, "title": title, "description": description}
        return {"key": model, "title": model, "description": "User added model"}

    def add_library_information(self):
        """Get information about models added by the user or in the library"""
        if len(self.models_info) == 0:
            return
        new_library = []
        for model in self.listed_models:
            new_library.append(self.get_info_for_library(model))
        for model in self.model_library:
            if model["key"] not in self.listed_models:
                new_library.append(self.get_info_for_library(model["key"]))
        self.model_library = new_library
        self.set_setting("model-library", self.model_library)

    def get_models(self, manual = False):
        """Get the list of installed models in ollama"""
        if not self.is_installed():
            return
        from ollama import Client 
        client = Client(
            host=self.get_setting("endpoint")
        )
        self.auto_serve(client)
        try:
            models = client.list()["models"]
        except Exception as e:
            if manual:
                self.throw("Can't get Ollama models: " + str(e), ErrorSeverity.WARNING)
            return
        res = tuple()
        for model in models:
            res += ((model.model, model.model), )
            if not self.model_in_library(model.model):
                self.model_library += [{"key": model.model, "title": model.model, "description": "User added model"}]
        self.models = res
        self.set_setting("models", json.dumps(self.models))
        self.set_setting("model-library", self.model_library)
        self.settings_update()

    def auto_serve(self, client):
        """Automatically runs ollama serve on the user system if it's not running and the setting is toggles

        Args:
            client (): ollama client 
        """
        if self.get_setting("serve") and can_escape_sandbox():
            try:
                client.ps()
            except Exception as e:
                Popen(get_spawn_command() + ["ollama", "serve"])
                time.sleep(1)

    def model_in_library(self, model) -> bool:
        for m in self.model_library:
            if m["key"] == model:
                return True
        return False

    @staticmethod
    def get_extra_requirements() -> list:
        return ["ollama"]

    def supports_vision(self) -> bool:
        return True

    def get_extra_settings(self) -> list:
        default = self.models[0][1] if len(self.models) > 0 else ""
        settings = [
            ExtraSettings.EntrySetting("endpoint", _("API Endpoint"), _("API base url, change this to use interference APIs"), "http://localhost:11434"),
            ExtraSettings.ToggleSetting("serve", _("Automatically Serve"), _("Automatically run ollama serve in background when needed if it's not running. You can kill it with killall ollama"), False),
            ExtraSettings.ToggleSetting("thinking", _("Enable Thinking"), _("Allow thinking in the model, only some models are supported"), True, website="https://ollama.com/search?c=thinking"),
            ExtraSettings.ToggleSetting("custom_model", _("Custom Model"), _("Use a custom model"), False, update_settings=True),
        ]
        if not self.get_setting("custom_model", False):
            settings.append(
                ExtraSettings.ComboSetting(
                    "model",
                    _("Ollama Model"),
                    _("Name of the Ollama Model"),
                    self.models,
                    default,
                    refresh= lambda x: self.get_models(manual=True),
                )
            )
        else:
            settings.append(
                ExtraSettings.EntrySetting("model", _("Ollama Model"), _("Name of the Ollama Model"), default)
            )
        if self.is_installed():
            settings.append(
                ExtraSettings.NestedSetting("model_manager", _("Model Manager"), _("List of models available"),
                    [
                        ExtraSettings.EntrySetting(
                            "extra_model_name",
                            _("Add custom model"),
                            _("Add any model to this list by putting name:size\nOr any gguf from hf with hf.co/username/model"),
                            "",
                            refresh=self.pull_model,
                            refresh_icon="plus-symbolic",
                            website="https://ollama.com/library"
                        )
                    ] + self.get_model_library(), refresh=lambda x : self.get_models_infomation
                )
            )
        settings.append(get_streaming_extra_setting())
        settings.append(ExtraSettings.ButtonSetting("update", _("Update Ollama"), _("Update Ollama"), lambda x: self.install(), _("Update Ollama")))
        return settings

    def pull_model(self, model: str):
        """Check if a model given by the user is downloadable, then add it to the library

        Args:
            model: name of the model 
        """
        from ollama import Client
        client = Client(
            host=self.get_setting("endpoint")
        )
        self.auto_serve(client)
        model = self.get_setting("extra_model_name")
        try:
            stream = client.pull(model, stream=True)
            for p in stream:
                if p.completed is not None:
                    print(p.completed)
                    break
        except Exception as e:
            print(e)
            return
        if not self.model_in_library(model):
            self.model_library = [{"key": model, "title": model, "description": "User added model"}] + self.model_library
        self.add_library_information()
        self.set_setting("model_library", self.model_library)
        self.set_setting("extra_model_name", "")
        self.settings_update()
        return

    def model_installed(self, model: str) -> bool:
        """Check if a model is installed by the user

        Args:
            model: name of the model 

        Returns:
            True if the model is installed 
        """
        for mod in self.models:
            if model == mod[0]:
                return True 
        return False

    def load_model(self, model):
        if not self.is_installed():
            return
        from ollama import Client
        client = Client(
            host=self.get_setting("endpoint")
        )
        self.auto_serve(client)
        return True

    def get_model_library(self) -> list:
        """Create extra settings to download models from the mode library

        Returns:
           extra settings 
        """
        res = []
        for model in self.model_library:
            s = ExtraSettings.DownloadSetting(model["key"], model["title"], model["description"], self.model_installed(model["key"]), self.install_model, self.get_percentage) 
            if not self.model_installed(model["key"]) and model["key"] not in self.listed_models:
                s["refresh"] = lambda x,m=model['key']: self.remove_model_from_library(m)
                s["refresh_icon"] = "minus-symbolic"
            res.append(s)
        return res

    def remove_model_from_library(self, model: str):
        """Remove a model from the library"""
        self.model_library = [x for x in self.model_library if x["key"] != model]
        self.set_setting("model_library", self.model_library)
        self.settings_update()

    def install_model(self, model: str):
        """Pulls/Deletes the model

        Args:
            model: model name 
        """
        from ollama import Client
        client = Client(
            host=self.get_setting("endpoint")
        )
        self.auto_serve(client)
        
        if self.model_installed(model):
            client.delete(model)
            self.get_models()
            return
        try:
            stream = client.pull(model, stream=True)
            for chunk in stream:
                if chunk.completed is None:
                    continue
                self.downloading[model] = chunk.completed/chunk.total
        except Exception as e:
            self.settings_update()
        self.get_models()    
        return
    
    def get_percentage(self, model: str):
        """Get the percentage of a currently downloading model

        Args:
            model: name of the model 

        Returns:
           percentage as float 
        """
        if model in self.downloading:
            return self.downloading[model]
        return 0
    

    def convert_history(self, history: list, prompts: list | None = None) -> list:
        """Convert history into ollama format"""
        if prompts is None:
            prompts = self.prompts
        result = []
        result.append({"role": "system", "content": "\n".join(prompts)})
        for message in history:
            if message["User"] == "Console":
                result.append({
                    "role": "user",
                    "content": "Console: " + message["Message"]
                })
            else:
                image, text = extract_image(message["Message"])
                
                msg = {
                    "role": message["User"].lower() if message["User"] in {"Assistant", "User"} else "system",
                    "content": text
                }
                if message["User"] == "User" and image is not None:
                    if image.startswith("data:image/png;base64,"):
                        image = image[len("data:image/png;base64,"):]
                    msg["images"] = [image]
                result.append(msg)
        return result
    
    def generate_text(self, prompt: str, history: list[dict[str, str]] = [], system_prompt: list[str] = []) -> str:
        from ollama import Client
        if self.get_setting("thinking") is False:
            prompt = "/no_think\n" + prompt
        history.append({"User": "User", "Message": prompt})
        messages = self.convert_history(history, system_prompt)

        client = Client(
            host=self.get_setting("endpoint")
        )

        self.auto_serve(client)
        try:
            response = client.chat(
                model=self.get_setting("model"),
                messages=messages,
            )
            return response["message"]["content"]
        except Exception as e:
            raise e
    
    def generate_text_stream(self, prompt: str, history: list[dict[str, str]] = [], system_prompt: list[str] = [], on_update: Callable[[str], Any] = lambda _: None, extra_args: list = []) -> str:
        from ollama import Client
        if self.get_setting("thinking") is False:
            prompt = "/no_think\n" + prompt
        history.append({"User": "User", "Message": prompt})
        messages = self.convert_history(history, system_prompt)
        client = Client(
            host=self.get_setting("endpoint")
        )
        
        self.auto_serve(client)
        try:
            response = client.chat(
                model=self.get_setting("model"),
                messages=messages,
                stream=True,
            )
            full_message = ""
            prev_message = ""
            for chunk in response:
                full_message += chunk["message"]["content"]
                args = (full_message.strip(), ) + tuple(extra_args)
                if len(full_message) - len(prev_message) > 1:
                    on_update(*args)
                    prev_message = full_message
            return full_message.strip()
        except Exception as e:
            raise e

