import time
import sys
import os
from huggingface_hub import InferenceClient
from pymongo import MongoClient

print("Starting...", flush=True)

api_key = os.getenv('API_KEY')

inference_client = InferenceClient(
	provider="hf-inference",
	api_key=api_key
)

# Define model paths and MongoDB URI
MONGO_URI = "mongodb://mongodb:27017"
DB_NAME = "imageUploadDB"

# Initialize MongoDB client and database
client = MongoClient(MONGO_URI)
db = client[DB_NAME]

try:
    # Test the connection by checking the server status
    client.admin.command('ping')
    print("MongoDB connection successful!")
except Exception as e:
    print("MongoDB connection failed:", e)

def get_pending_jobs():
    """
    This function retrieves all entries with the status 'analyzed' from all collections,
    sorted by upload date (oldest first).
    """
    pending_jobs = []

    # Iterate through all collections in the database
    for collection_name in db.list_collection_names():
        collection = db[collection_name]

        # Find all entries with the status 'uploaded' and sort by upload date
        jobs = collection.find({"status": "analyzed"}).sort("uploadDate", 1)  # 1 for ascending order
        # Add the found jobs to the pending jobs list
        for job in jobs:
            pending_jobs.append({
                "collection": collection_name,
                "entry": job
            })

    # Sort the entire list of pending jobs by creation date
    pending_jobs.sort(key=lambda x: x["entry"]["uploadDate"])

    return pending_jobs


def create_prompt():
    jobs = get_pending_jobs()
    if not jobs:
        print("No pending jobs!")
        return

    while jobs:  # Continue processing until the job list is empty
        oldest_job = jobs.pop(0)  # Remove and get the first job from the list
        print(f"Processing job with id: {oldest_job['entry']['_id']}")
        
        collection_name = oldest_job['collection']
        collection = db[collection_name]

        # Update the status in the database to "create_image"
        collection.update_one(
            {"_id": oldest_job['entry']['_id']}, 
            {"$set": {"status": "prompting"}}
        )

        try:
            # Extract prompt
            frontImageDescription = oldest_job['entry']["frontImageDescription"]
            backImageDescription = oldest_job['entry']["backImageDescription"]
            emotion = oldest_job['entry']["emotion"]

            print("Creating prompt")

            # Update the status in the database to "generating"
            collection.update_one(
                {"_id": oldest_job['entry']['_id']}, 
                {"$set": {"status": "prompting"}}
            )


            # Define the prompt template
            prompt_template = "Generate a detailed prompt of a person and a scene based on image descriptions and their emotional state. Given the following inputs:\n\n1. Front image description: {frontImageDescription}\n2. Back image description: {backImageDescription}\n3. Emotion: {emotion} \n\nFill in the following template with the relevant information:\n'A [skin color] [gender] with [hair color and style], [eye color], expressing [emotion] intensely, wearing [clothing], in a setting where [summarized back image description in about 20 words].'\nFor the parameter 'summarized back image description,' condense the provided back image description into approximately 20 words. Ensure logical consistency and avoid adding unrelated details. Output only the final prompt in plain text, without any extra characters or formatting."
            prompt_template2 = "Generate concise German captions that convey the specified emotion based on FrontImage and BackImage descriptions.\nFormat: Ich bin [emotion]. [Creative phrase fitting the scene].\nReplace [emotion] with the German equivalent of {emotion}.\nUse {frontImageDescription} and {backImageDescription} in the second sentence.\nKeep it brief—maximum 10 words total.\nExample: Ich bin glücklich. Die Pizza war lecker."
            

            # Format the prompt
            prompt = prompt_template.format(frontImageDescription=frontImageDescription, backImageDescription=backImageDescription, emotion=emotion)
            prompt2 = prompt_template2.format(frontImageDescription=frontImageDescription, backImageDescription=backImageDescription, emotion=emotion)
            
            print(prompt)
            print("\n")
            print(prompt2)

            messages = [
            	{
            		"role": "user",
            		"content": prompt
            	}
            ]

            messages2 = [
            	{
            		"role": "user",
            		"content": prompt2
            	}
            ]

            completion = inference_client.chat.completions.create(
                model="mistralai/Mistral-Nemo-Instruct-2407", 
            	messages=messages, 
            	max_tokens=300
            )

            completion2 = inference_client.chat.completions.create(
                model="mistralai/Mistral-Nemo-Instruct-2407", 
            	messages=messages2, 
            	max_tokens=300
            )

            result = completion.choices[0].message.content + ", icon emoji"
            result2 = completion2.choices[0].message.content
            print(result)
            print(result2)

            collection.update_one(
                    {"_id": oldest_job['entry']['_id']}, 
                    {"$set": {"prompt": result}}
            )

            collection.update_one(
                    {"_id": oldest_job['entry']['_id']}, 
                    {"$set": {"caption": result2}}
            )
            
            #Update the status in the database to "prompt_created"
            collection.update_one(
                {"_id": oldest_job['entry']['_id']}, 
                {"$set": {"status": "prompted"}}
            )

        except Exception as e:
            print(f"Error analyzing image for job {oldest_job['entry']['_id']}: {e}")

# Infinite loop with 15 seconds interval
while True:
    try:
        create_prompt()
    except Exception as e:
        print("Error: ", e)
    print("Warte 15 Sekunden...", flush=True)
    time.sleep(15)  # Wait for 15 seconds
    sys.stdout.flush()  # Explicitly flush output
