from flask import Flask, render_template, request, jsonify
from model import FormModel

app = Flask(__name__, template_folder='templates', static_folder='static')


@app.route('/api/parse', methods=['POST'])
def parse_form_controller():
    data = request.get_json()
    form_url = data.get('url')

    if not form_url:
        return jsonify({'error': 'Ссылка не передана'}), 400

    form_options = FormModel.parse_form(form_url)
    if not form_options:
        return jsonify({'error': 'Не удалось спарсить форму или неверная ссылка'}), 400

    return jsonify({'formOptions': form_options})


@app.route('/api/submit', methods=['POST'])
def submit_form_controller():
    data = request.get_json()
    form_url = data.get('url')
    form_options = data.get('formOptions')
    counts_map = data.get('countsMap', {})
    total = int(data.get('total', 1))
    mode = data.get('mode', 'random')

    try:
        sent_count = FormModel.submit_payloads(form_url, form_options, counts_map, total, mode)
        return jsonify({'success': True, 'sent': sent_count, 'total': total})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/')
def index():
    return render_template('index.html')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)