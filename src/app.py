import imghdr
import os
import glob
from flask import Flask, render_template, request, redirect, url_for, abort, \
    send_from_directory, jsonify
from werkzeug.utils import secure_filename
import uuid
# from waitress import serve

# Image Caption module
import numpy as np
import matplotlib.pyplot as plt
from img2_caption import load_models, predict
from PIL import Image
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import matplotlib 
matplotlib.use('Agg')

# GPT2 Module
from gpt2 import generate_story, load_model, create_paragraphing_html


app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024
app.config['UPLOAD_EXTENSIONS'] = ['.jpg', '.png', '.jpeg']
app.config['UPLOAD_PATH'] = 'static/uploads/'
app.config['PLOT_PATH'] = 'static/plot/'

# Load img_caption model
image_features_extract_model, tokenizer, encoder, decoder = load_models()
result_list = []  # init empty result list

# Load GPT2 model
model = load_model()


def plot_attention(image, result, attention_plot):
    temp_image = np.array(Image.open(image))

    fig = plt.figure(figsize=(10, 10))

    # https://stackoverflow.com/questions/12319796/dynamically-add-create-subplots-in-matplotlib
    Tot = len(result)
    Cols = 3

    # Compute Rows required
    Rows = Tot // Cols
    Rows += Tot % Cols

    # Create a Position index
    Position = range(1, Tot + 1)

    for l in range(Tot):
        temp_att = np.resize(attention_plot[l], (8, 8))
        ax = fig.add_subplot(Rows, Cols, Position[l])
        ax.set_title(result[l], fontsize=30)
        img = ax.imshow(temp_image)
        ax.imshow(temp_att, cmap='gray', alpha=0.6, extent=img.get_extent())

    plt.tight_layout()
    return fig


def validate_image(stream):
    """
    Ensure the images are valid and in correct format

    Args:
        stream (Byte-stream): The image

    Returns:
        str: return image format
    """
    header = stream.read(512)
    stream.seek(0)
    format = imghdr.what(None, header)
    if not format:
        return None
    return '.' + (format if format != 'jpeg' else 'jpg')


def del_dir_files(files_path):
    """
    Delete all user upload temp image files in the directory after reload

    Args:
        files_path (str): path of images
    """
    existing_files = os.path.join(files_path, '*')
    file_to_delete = glob.glob(existing_files)
    for i in file_to_delete:
        os.remove(i)


@app.errorhandler(413)
def too_large(e):
    """ Check if file size is too large """
    return "File is too large", 413


@app.route('/')
def index():
    """
    Render index.html and delete all the image files in static/uploads

    Returns:
        Render Html: Rendered index.html
    """

    result_list[:] = []  # clear result list

    # Cleanup all the image files in static/uploads.
    del_dir_files(app.config['UPLOAD_PATH'])
    del_dir_files(app.config['PLOT_PATH'])
    # existing_files = os.path.join(app.config['UPLOAD_PATH'], '*')
    # file_to_delete = glob.glob(existing_files)
    # for i in file_to_delete:
    #     os.remove(i)

    return render_template('index.html')


@app.route('/', methods=['POST'])
def upload_files():
    """
    Upload the image to static/uploads folder and validate the filename and 
    extension .jpg .png

    Returns:
        empty string: 204 No Content success status response code
    """
    uploaded_file = request.files['file']
    filename = secure_filename(uploaded_file.filename)
    if filename != '':
        file_ext = os.path.splitext(filename)[1]
        if file_ext not in app.config['UPLOAD_EXTENSIONS'] or \
                file_ext != validate_image(uploaded_file.stream):
            return "Invalid image", 400
        uploaded_file.save(os.path.join(app.config['UPLOAD_PATH'], filename))

    return '', 204


@app.route('/image_caption', methods=["GET", "POST"])
def image_caption():
    """
    Predict and display the result

    Returns:
        Json: Return the filename of the images and the generated story 
                for each image
    """
    image_names = os.listdir(app.config['UPLOAD_PATH'])

    caption_image_list = []
    plot_image_name = []

    for i in image_names:
        result, attention_plot = predict(os.path.join(
            app.config['UPLOAD_PATH'], i), image_features_extract_model,
            tokenizer, encoder, decoder)

        # generate random filename
        filename = str(uuid.uuid4())

        fig = plot_attention(os.path.join(
            app.config['UPLOAD_PATH'], i), result, attention_plot)
        fig.savefig(app.config['PLOT_PATH'] + filename + '.png', bbox_inches='tight',
                    pad_inches=0)

        plot_image_name.append(filename + '.png')
        del result[-1]  # remove the last element "<end>"
        result_list.append(result)
        caption = ' '.join(result).capitalize()
        caption_image_list.append(caption)

    return jsonify(caption_image_list=caption_image_list, image_names=image_names,
                   plot_image_name=plot_image_name)


@app.route('/display_image', methods=["GET", "POST"])
def display_image():
    """
    Predict and display the result

    Returns:
        Json: Return the filename of the images and the generated story 
                for each image
    """
    image_names = os.listdir(app.config['UPLOAD_PATH'])

    caption_list = []
    text_list = []

    j = 0

    for i in image_names:
        # result, attention_plot = predict(os.path.join(
        #     app.config['UPLOAD_PATH'], i), image_features_extract_model,
        #     tokenizer, encoder, decoder)

        result = result_list[j]
        caption_title = f"'{' '.join(result[-3:]).capitalize()}'"
        caption = ' '.join(result)
        generate_txt = generate_story(caption, model)
        generate_txt = create_paragraphing_html(generate_txt)
        caption_list.append(caption_title)
        text_list.append(generate_txt)

        j += 1

    return jsonify(caption_list=caption_list, image_names=image_names,
                   text_list=text_list)


if __name__ == "__main__":
    app.run(debug=True, port=8000)
    # Use gunicorn for serving in production
