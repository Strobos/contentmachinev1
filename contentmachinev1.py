import openai
import csv
import time
import os
import string
from tqdm import tqdm
import openai.error
import json

# Initialize the OpenAI API client
openai.api_key = "your-api-key"

def get_topic_and_sections(filename):
    with open(filename, newline='', encoding='utf-8') as file:
        reader = csv.reader(file)
        for row in reader:
            topic = row[0]
            sections = []
            for i in range(1, 16, 2):
                if row[i]:
                    sections.append((row[i], row[i + 1].splitlines()))
            yield topic, sections

def make_api_call(prompt, max_tokens, conversation_history="", retries=3, delay=10):
    prompt_with_history = conversation_history + prompt
    for attempt in range(retries):
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": "You are writerGPT. You never use placeholder content. You create articles. ..."
                    },
                    {
                        "role": "user",
                        "content": prompt_with_history
                    }
                ],
                max_tokens=max_tokens
            )
            new_conversation_history = conversation_history + response['choices'][0]['message']['content']
            return response['choices'][0]['message']['content'], new_conversation_history
        except openai.error.OpenAIError as e:
            print(f"API error: {e}, attempting again in {delay} seconds... ({attempt + 1}/{retries})")
            time.sleep(delay)
    print(f"Request failed after {retries} attempts.")
    return None, conversation_history

def generate_image(prompt):
    try:
        response = openai.Image.create(
            prompt=prompt,
            n=1,
            size="1024x1024"
        )
        image_url = response['data'][0]['url']
        return image_url
    except openai.error.OpenAIError as e:
        print(f"Failed to generate image due to an API error: {e}")
        return None

def sanitize_filename(filename):
    valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
    filename = ''.join(c for c in filename if c in valid_chars)
    filename = filename.replace(' ', '_')
    return filename

def create_key_takeaways_table(article_content):
    takeaways_prompt = f"Create a key takeaways column in table format which gives all the information that..."
    
    takeaways_content, _ = make_api_call(takeaways_prompt, 512)
    return takeaways_content if takeaways_content else "Key takeaways generation failed."

def generate_seo_details(keyword, idx):
    base_filename = sanitize_filename(keyword)
    seo_details = {
        "filename": f"{idx}_{base_filename}.png",
        "alt_text": f"{keyword} in an image",
        "title": f"Illustration of {keyword}",
        "description": f"A visual representation of {keyword}."
    }
    seo_details["alt_text"] = seo_details["alt_text"][:125]
    seo_details["title"] = seo_details["title"][:55]
    return seo_details

def save_image_seo_details(article_directory, topic, seo_details, idx):
    sanitized_topic = sanitize_filename(topic)
    filename = f"{idx}_seo_details_{sanitized_topic}.json"
    path = os.path.join(article_directory, filename)
    with open(path, "w", encoding='utf-8') as file:
        json.dump(seo_details, file, indent=4)

def main():
    article_directory = "articles"
    if not os.path.exists(article_directory):
        os.makedirs(article_directory)

    for idx, (topic, sections) in enumerate(tqdm(get_topic_and_sections("keywords.csv")), start=1):
        print(f"\nProcessing {idx}. {topic}")
        conversation_history = ""
        article_content = ""
        key_takeaways_table = ""
        
        for i, (title, description_lines) in enumerate(sections, start=1):
            description = "\n".join(f"- {line}" for line in description_lines)
            section_prompt = f"## {title}\n{description}\n\nWrite a detailed section based on the above subheading ..."
            
            section_content, conversation_history = make_api_call(section_prompt, 2048, conversation_history)
            
            if section_content is None:
                print(f"Failed to generate content for {title}, skipping...")
                continue

            if i == 1:
                key_takeaways_table = create_key_takeaways_table(section_content)
            
            article_content += f"## {title}\n{section_content}\n\n"
            
            if key_takeaways_table and i == 1:
                article_content += f"{key_takeaways_table}\n\n"

            # Generate images for each section and store corresponding SEO details
            section_image_url = generate_image(f"An image for the section: {title}")
            if section_image_url:
                seo_details = generate_seo_details(title, i)
                save_image_seo_details(article_directory, topic, seo_details, i)
                image_markdown = f"![{seo_details['alt_text']}]({section_image_url})"
                article_content += f"{image_markdown}\n\n"

        if not article_content:
            print(f"No content generated for {topic}, skipping...")
            continue

        featured_image_url = generate_image(f"An image illustrating the concept of {topic}")
        if featured_image_url is None:
            print(f"Failed to generate image for {topic}, skipping...")
            continue
        
        seo_details = generate_seo_details(topic, 0)
        save_image_seo_details(article_directory, topic, seo_details, 0)
        featured_image_markdown = f"![{seo_details['alt_text']}]({featured_image_url})\n\n"
        
        sanitized_topic = sanitize_filename(topic)
        with open(os.path.join(article_directory, f"{idx}. {sanitized_topic}.md"), "w", encoding='utf-8') as file:
            file.write(f"# {topic}\n\n{featured_image_markdown}{article_content}")

        print(f"Completed {idx}. {topic}")

if __name__ == "__main__":
    main()