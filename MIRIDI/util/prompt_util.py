from langchain import PromptTemplate
import os
import json
# from concurrent.futures import ThreadPoolExecutor, as_completed
from jinja2 import Template
from tqdm import tqdm
import boto3

# 모델 ID와 결과 파일 접미사 매핑
# MODELS = {
#    "anthropic.claude-3-haiku-20240307-v1:0": "haiku3",
#    "anthropic.claude-3-5-sonnet-20240620-v1:0": "sonnet35",    
# }

def print_json(data):
    print(json.dumps(data, indent = 3,ensure_ascii=False))

def load_template_from_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        template_content = file.read()
    return template_content


import time

def invoke_claude(prompt):
    bedrock = boto3.client(service_name="bedrock-runtime")
    body = json.dumps({
        "max_tokens": 4196,
        "messages": [{"role": "user", "content": prompt}],
        "anthropic_version": "bedrock-2023-05-31"
    })
    
    time.sleep(120)  # Add a small delay to avoid rate limiting
    response = bedrock.invoke_model(body=body, modelId="anthropic.claude-3-5-sonnet-20240620-v1:0")
    # print("bedrock.invoke_model 호출 완료\n")
    response_body = json.loads(response.get("body").read())
    output_text = response_body.get("content")[0].get('text')

    print(output_text)
    # print("호출")
    
    input_token_count = int(response["ResponseMetadata"]["HTTPHeaders"]["x-amzn-bedrock-input-token-count"])
    output_token_count = int(response["ResponseMetadata"]["HTTPHeaders"]["x-amzn-bedrock-output-token-count"])
    
    return output_text, input_token_count, output_token_count

def print_slide_titles(json_data):
    # JSON 문자열을 Python 딕셔너리로 파싱
    data = json.loads(json_data) if isinstance(json_data, str) else json_data
    
    # 메인 타이틀 출력
    print(f"프레젠테이션 제목: {data['title']}\n")
    
    # 슬라이드 리스트를 순회하며 각 슬라이드의 제목 출력
    for slide in data['slides']:
        print(f"슬라이드 {slide['slide_number']}: {slide['slide_title']}")




def create_slide_prompt(outline, slide_prompt_template, topic, include_outline=True, max_slide_num=3):
    # JSON 문자열을 Python 딕셔너리로 파싱
    data = json.loads(outline) if isinstance(outline, str) else outline
    
    
    # 슬라이드 리스트를 순회하며 각 슬라이드의 제목 출력
    slide_prompt_list = []
    for i, slide in enumerate(data['slides']):
        if ( i == max_slide_num):
            break

        slide_title = slide['slide_title']
        slide_number = slide['slide_number']

        if include_outline:
            slide_prompt = slide_prompt_template.render(topic=topic, 
                                                outline=outline, 
                                                slide_number=slide_number,
                                                slide_title=slide_title,
                                                )
        else:
            slide_prompt = slide_prompt_template.render(topic=topic, 
                                                outline="Not Available", 
                                                slide_number=slide_number,
                                                slide_title=slide_title,
                                                )

        slide_prompt_list.append(slide_prompt)
        print("## slide_prompt: \n", slide_prompt)

    return slide_prompt_list

def create_part_slide_prompt(outline, slide_prompt_template, topic, include_outline=True, n_slide = 1, max_slide_num=3):
    # JSON 문자열을 Python 딕셔너리로 파싱
    data = json.loads(outline)
    
    f=0

    # slide_number와 slide_title 추출
    slides = [(slide['slide_number'], slide['slide_title']) for slide in data['slides']]
    

    # 슬라이드 리스트를 순회하며 각 슬라이드의 제목 출력
    slide_prompt_list = []

    # 각 그룹 크기에 대해 처리
    group_sizes = [n_slide]
    for size in group_sizes:
        # print(f"\n그룹 크기 {size}:")
        for i in range(0, len(slides), size):
            if ( i == max_slide_num):
                break
            slide_group = slides[i:i+size]
            slide_number = [slide[0] for slide in slide_group]
            slide_title_group = [slide[1] for slide in slide_group]

            if include_outline:
                slide_prompt = slide_prompt_template.render(topic=topic, 
                                                outline=outline, 
                                                slide_number=slide_number,
                                                slide_title=slide_title_group,
                                                )
            else:
                slide_prompt = slide_prompt_template.render(topic=topic, 
                                                outline="Not Available", 
                                                slide_number=slide_number,
                                                slide_title=slide_title_group,
                                                )
            slide_prompt_list.append(slide_prompt)
            f=f+1
            print(f"## {f}th call's slide_prompt: \n", slide_prompt)
            print("\n")

    return slide_prompt_list





def generate_slide_content(slide_prompt_list, output_dir, include_outline):
    slides = [] 
    total_input_tokens = 0 
    total_output_tokens =0

    for i, slide_prompt in enumerate(slide_prompt_list):
        print(f"{i+1}번째 호출 시작합니다.\n")
        slide_content, input_tokens, output_tokens = invoke_claude(slide_prompt)
        # slides.append(f"Slide {i+1}:\n{slide_content}")
        slides.append(f"{slide_content}")

        # Print all slides
        print("\n Detailed Slide Contents:")
        for slide in slides:
            print(slide)
            print("\n" + "-"*50 + "\n")

        print(f"{i+1}번째 호출: Input tokens: {input_tokens}, Output tokens: {output_tokens} \n")
        
        total_input_tokens += input_tokens
        total_output_tokens += output_tokens

        # time.sleep(120)  # Add a small delay to avoid rate limiting
        

    print("\n" + "="*50 + "\n")
    print("PowerPoint presentation generation complete!")
    print(f"Total Input Tokens: {total_input_tokens}")
    print(f"Total Output Tokens: {total_output_tokens}")

    if include_outline: 
        output_file = f"result_include_outline_each_slide.txt"
    else:
        output_file = f"result_exclude_outline_each_slide.txt"
    output_path = os.path.join(output_dir, output_file)
    with open(output_path, "w", encoding="utf-8") as f:
        for slide in slides:
            f.write(slide)
            f.write("\n" + "-"*50 + "\n")

    print(f"Processed and saved: {output_path}")




def invoke_all_claude(prompt):
    bedrock = boto3.client(service_name="bedrock-runtime")
    body = json.dumps({
        "max_tokens": 4196,
        "messages": [{"role": "user", "content": prompt}],
        "anthropic_version": "bedrock-2023-05-31"
    })
    
    response = bedrock.invoke_model(body=body, modelId="anthropic.claude-3-5-sonnet-20240620-v1:0")
    response_body = json.loads(response.get("body").read())
    return response_body.get("content")[0].get('text'), int(response["ResponseMetadata"]["HTTPHeaders"]["x-amzn-bedrock-output-token-count"])


def generate_all_slide_content(presentation_prompt, output_dir):

    presentation_content, total_output_tokens = invoke_all_claude(presentation_prompt)

    print("Generated Presentation Content:")
    print(presentation_content)
    print("\n" + "="*50 + "\n")
    print(f"Total output tokens: {total_output_tokens}")
    print("PowerPoint presentation generation complete!")

    # Optional: Split the content into individual slides
    slides = presentation_content.split("Slide")[1:]  # Split by "Slide" and remove empty first element
    slides = ["Slide" + slide for slide in slides]  # Add "Slide" back to each element

    print("\nIndividual Slides:")
    # for slide in slides:
    #     print(slide.strip())
    #     print("\n" + "-"*50 + "\n")


    output_file = f"result_all_slide.txt"
    output_path = os.path.join(output_dir, output_file)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(presentation_content)

    print(f"Processed and saved: {output_path}")

