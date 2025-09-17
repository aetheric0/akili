import os
import requests
import json

# --- Configuration ---
# IMPORTANT: Get your API key from Google AI Studio and save it here.
# For better security, you should use environment variables in a real app.
API_KEY = ""

# The text you want to process
YOUR_TEXT = """
HCI Introduction Historical perspective During the technology explosion of the 1970s, the notion of the user interface, also known as the Man-Machine Interface (MMI), became a general concern to both system designers and researchers. User interface refers to the elements of the system the user comes into contact with, when interacting with the system. The user interface provides: •  an input language for the user, •  an output language for the machine, and •  a protocol for interaction Computer companies realized that if they could improve the physical aspects of the user interface, they would stand a better chance of being successful in the marketplace, and thus the cliché ‘user friendly’ evolved. However most companies were not really improving the user interfaces but were rather using the term as a marketing ploy, paying lip service to the real issues. In the mid-1980s, the term Human-Computer Interaction (HCI) was adopted as a means of describing this then new field of study. •  This term acknowledged that the focus was broader than just the design of the user interface, and was concerned with all those of that relate to the interaction between users and computers (e.g. working practices, social interactions, user characteristics, user capabilities, user preferences, training issues, health hazards, organizational issues, etc). •  The term did not imply gender-bias!What is HCI HCI is a discipline concerned with the design, evaluation and implementation of interactive computing systems for human use and with the study of major phenomena surrounding them. It involves the design, evaluation and implementation of interactive systems in the context of the user’s task and work. •  User – an individual user, a group of users working together, or a sequence of users in an organization, each dealing with some part of the task or process. The user is whoever is trying to get the job/task done using the computing technology. •  Computer – any technology ranging from the general desktop computer to a large scale computer system, a process control system, an embedded system or a ubiquitous system. •  Interaction – any communication between a user and computer. It can be direct interaction or indirect interaction. •  Direct interaction involves a dialog with feedback and control throughoutperformance of the task. Indirect interaction may involve batch processing or intelligent sensors controlling the environment. Underlying all HCI research and design is the belief that people using a computer system should come first. Their needs, capabilities, goals, and preferences for performing various activities should inform the ways in which systems are designed and implemented. Who is involved in HCI HCI ideally involves expertise from many disciplines. For instance: •  Psychology and cognitive science: to understand the user’s perceptual, cognitive and problem-solving skills. •  Ergonomics: for the user’s physical capabilities. •  Sociology: to understand the wider context of the interaction. •  Computer science and engineering: to be able to design and build the necessary technology. •  Etc HCI is therefore an interdisciplinary subject. In practice people tend to take a strong stance on one side or another. In this course we will take a stance on computer science [as is often the case].
"""

# --- Prompts ---
SUMMARY_PROMPT = f"Generate a concise, easy-to-understand summary of the following text: {YOUR_TEXT}"
QUIZ_PROMPT = f"Based on the following text, create a 5-question multiple-choice quiz. Provide an answer key at the end. TEXT: {YOUR_TEXT}"

# --- API Call Function ---
def generate_content(prompt_text):
    """
    Function to make a direct API call to the Gemini API.
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={API_KEY}"

    headers = {
        'Content-Type': 'application/json',
    }

    data = {
        "contents": [{
            "parts": [{
                "text": prompt_text
            }]
        }]
    }

    print(f"--- Sending request for: {prompt_text[:30]}... ---")
    response = requests.post(url, headers=headers, data=json.dumps(data))

    if response.status_code == 200:
        # The actual text is nested deep inside the JSON response
        result_json = response.json()
        # This line navigates the JSON to get the text part
        return result_json['candidates'][0]['content']['parts'][0]['text']
    else:
        return f"Error: {response.status_code}\n{response.text}"

# --- Main Execution ---
if __name__ == "__main__":
    print("--- Generating Study Pack ---")

    # 1. Generate Summary
    summary = generate_content(SUMMARY_PROMPT)
    print("\n--- Summary ---")
    print(summary)

    # 2. Generate Quiz
    quiz = generate_content(QUIZ_PROMPT)
    print("\n--- Quiz ---")
    print(quiz)

    print("\n--- Mission Complete ---")