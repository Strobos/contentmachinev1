import openai
import csv
import time
import os
import string
from tqdm import tqdm
import openai.error
import json

# Initialize the OpenAI API client
openai.api_key = "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"

def get_topic_and_sections(filename):
    with open(filename, newline='', encoding='utf-8') as file:
        reader = csv.reader(file)
        for row in reader:
            topic = row[0]
            sections = []
            for i in range(1, 16, 2):  # Process pairs of columns for titles and descriptions
                if row[i]:  # Check if the section title exists
                    sections.append((row[i], row[i + 1].splitlines()))  # Split the description into bullet points
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
                        "content": "You are writerGPT. You never use placeholder content. Your mission is to craft top-tier, SEO-optimized content for PrehistoricSaurus.com, ensuring every article resonates with both search engines and readers alike. Start with a compelling H1 title, followed by organized content under H2 and H3 headers using markdown for format. Ground your writing in verified facts, presenting metrics in both meters and kilograms, with conversions in parentheses. Balance your articles with lists where appropriate, maintaining simplicity and readability throughout. Your blog posts should exhibit a spectrum of sentence lengths and structures, infused with creativity, perplexity, and burstiness. Remember to weave the target keyword and its variations fluidly into the text, alongside LSI and NLP keyword strategies, to enhance the article's relevance and discoverability. Consistency in tone and style is key; captivate your audience from the introduction and sustain their interest with human-like storytelling, practical examples, and relatable experiences. Active voice and transition words will make your content flow smoothly. To enhance user engagement, intersperse tables within the text, ensuring no section feels like a monotonous block. Integrate external links to authoritative sources using natural anchor text, contributing to the article's informative value and helping readers achieve their goals. Your article should be accessible to a wide audience, from adults to 8th graders, without leading teasers or cliffhangers to the next section. Follow these guidelines to create original, engaging, and informative blog posts that stand out in the vast ocean of online content."
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
            size="1280x720"
        )
        image_url = response['data'][0]['url']
        return image_url
    except openai.error.OpenAIError as e:
        print(f"Failed to generate image due to an API error: {e}")
        return None

def sanitize_filename(filename):
    valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
    filename = ''.join(c for c in filename if c in valid_chars)
    filename = filename.replace(' ', '_')  # replace spaces with underscores for Windows compatibility
    return filename

def create_key_takeaways_table(article_content):
    takeaways_prompt = f"Create a key takeaways column in table format which gives all the information that someone needs from this article and answers all their questions:\n\n{article_content}"
    
    takeaways_content, _ = make_api_call(takeaways_prompt, 512)
    return takeaways_content if takeaways_content else "Key takeaways generation failed."

def generate_seo_details(keyword, image_prompt, idx):
    base_filename = sanitize_filename(keyword)
    # Ensure the image prompt is suitable for the following alt, title, and description
    simplified_prompt = image_prompt.replace('\n', ' ').replace('  ', ' ').strip()
    simplified_prompt = (simplified_prompt[:100] + '...') if len(simplified_prompt) > 100 else simplified_prompt
    
    seo_details = {
        "filename": f"{idx}_{base_filename}.png",
        "alt_text": f"{keyword} - {simplified_prompt}".strip()[:125],
        "title": f"{keyword}: {simplified_prompt}".strip()[:55],
        "description": f"{keyword} - A visual depiction: {simplified_prompt}".strip()
    }
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
        
        # Process each section and generate content
        for i, (title, description_lines) in enumerate(sections, start=1):
            description = "\n".join(f"- {line}" for line in description_lines)
            section_prompt = f"## {title}\n{description}\n\nWrite a detailed section based on the above subheading and bullet points:"
            
            section_content, conversation_history = make_api_call(section_prompt, 2048, conversation_history)
            if section_content is None:
                print(f"Failed to generate content for {title}, skipping...")
                continue  # Skip this section if the request failed

            # If this is the first section (introduction), generate key takeaways
            if i == 1:
                key_takeaways_table = create_key_takeaways_table(section_content)
            
            # Append the section content to the article content
            article_content += f"## {title}\n{section_content}\n\n"
            
            # If key takeaways were generated, insert them after the first section
            if key_takeaways_table and i == 1:
                article_content += f"{key_takeaways_table}\n\n"

            # Generate images for each section and store corresponding SEO details
            section_image_prompt = f"An image for the section: {title}"
            section_image_url = generate_image(section_image_prompt)
            if section_image_url:
                seo_details = generate_seo_details(title, section_image_prompt, i)
                save_image_seo_details(article_directory, topic, seo_details, i)
                image_markdown = f"![{seo_details['alt_text']}]({section_image_url})"
                article_content += f"{image_markdown}\n\n"

        if not article_content:
            print(f"No content generated for {topic}, skipping...")
            continue

        # Generate the featured image at the top of the article
        featured_image_prompt = f"An image illustrating the concept of {topic}"
        featured_image_url = generate_image(featured_image_prompt)
        if featured_image_url is None:
            print(f"Failed to generate image for {topic}, skipping...")
            continue
        featured_seo_details = generate_seo_details(topic, featured_image_prompt, 0)
        save_image_seo_details(article_directory, topic, featured_seo_details, 0)
        featured_image_markdown = f"![{featured_seo_details['alt_text']}]({featured_image_url})\n\n"

        sanitized_topic = sanitize_filename(topic)
        with open(os.path.join(article_directory, f"{idx}. {sanitized_topic}.md"), "w", encoding='utf-8') as file:
            # Place the image markdown at the top, followed by the article content
            file.write(f"# {topic}\n\n{featured_image_markdown}{article_content}")

        print(f"Completed {idx}. {topic}")

if __name__ == "__main__":
    main()
