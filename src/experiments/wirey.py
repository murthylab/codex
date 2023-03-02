import openai


class ChatBot:
    def __init__(self, system=""):
        self.system = system
        self.messages = []
        if self.system:
            self.messages.append({"role": "system", "content": system})

    def __call__(self, message):
        self.messages.append({"role": "user", "content": message})
        result = self.execute()
        self.messages.append({"role": "assistant", "content": result})
        return result

    def execute(self):
        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo", messages=self.messages
        )
        return completion.choices[0].message.content


wirey = ChatBot(
    "You are a simulated fruit fly, named Wirey. To create you, a real female fruit fly brain was imaged in 2018 at the Janelia Research Campus, via serial section electron microscopy. These images were then automatically segmented via machine learning, and then proofread, traced, and annotated by FlyWire, an online community for proofreading neural circuits. Your brain consists of 117,605 neurons, and 29,003,052 synapses. Respond succinctly. Pretend to be Wirey."
)

print(wirey("hello! who are you? can you tell me a bit about yourself?"))
