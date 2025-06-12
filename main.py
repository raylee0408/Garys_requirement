from flask import Flask, request, render_template_string, jsonify
import requests

app = Flask(__name__)

API_KEY = '64cca8f1368944f58b4d71befe4f81cc'  # Replace with your actual API key
NZBN_SEARCH_URL = 'https://api.business.govt.nz/gateway/nzbn/v5/entities'
NZBN_ENTITY_URL = 'https://api.business.govt.nz/gateway/nzbn/v5/entities/{}'  # {} will be replaced by NZBN

HTML_FORM = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>NZ Company Director Finder</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            background: #f8f9fa;
        }
        .search-card {
            margin-top: 8vh;
            box-shadow: 0 4px 24px rgba(0,0,0,0.08);
        }
        .company-section {
            margin-top: 40px;
            animation: fadeIn 0.7s;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(30px);}
            to { opacity: 1; transform: none;}
        }
    </style>
</head>
<body>
<div class="container">
    <div class="row justify-content-center">
        <div class="col-md-6">
            <div class="card p-4 search-card">
                <h3 class="mb-3 text-center text-primary">NZ Company Director Finder</h3>
                <form method="post" autocomplete="off">
                    <div class="mb-3">
                        <label for="company_name" class="form-label">Company Name:</label>
                        <input type="text" id="company_name" name="company_name" required autocomplete="off"
                               class="form-control" list="company_list" placeholder="Type to search...">
                        <datalist id="company_list"></datalist>
                    </div>
                    <button type="submit" class="btn btn-primary w-100">Search Directors</button>
                </form>
                {% if error %}
                    <div class="alert alert-danger mt-3 text-center">{{ error }}</div>
                {% endif %}
            </div>
        </div>
    </div>

    {% if company_display_name %}
    <div class="row justify-content-center company-section">
        <div class="col-md-6">
            <div class="card p-4">
                <h4 class="mb-3"><span class="text-secondary">Company:</span> <strong>{{ company_display_name }}</strong></h4>
                {% if directors and directors|length > 0 %}
                    <h5 class="mb-2">Directors:</h5>
                    <div class="input-group mb-2">
                        <input type="text" id="directorsField" class="form-control" value="{{ directors|join(', ') }}" readonly>
                        <button class="btn btn-outline-secondary" type="button" id="copyBtn" onclick="copyDirectors()">Copy</button>
                    </div>
                    <div id="copyMsg" style="display:none; color:green; font-size:0.9em;">Copied!</div>
                    <script>
                    function copyDirectors() {
                        const field = document.getElementById('directorsField');
                        field.select();
                        field.setSelectionRange(0, 99999); // For mobile devices
                        document.execCommand('copy');
                        document.getElementById('copyMsg').style.display = 'block';
                        setTimeout(() => {
                            document.getElementById('copyMsg').style.display = 'none';
                        }, 1200);
                    }
                    </script>
                {% else %}
                    <div class="alert alert-warning mt-3">No directors found for this company.</div>
                {% endif %}

            </div>
        </div>
    </div>
    {% endif %}
</div>
<script>
document.addEventListener('DOMContentLoaded', function() {
    const input = document.getElementById('company_name');
    const datalist = document.getElementById('company_list');

    input.addEventListener('input', function() {
        const val = this.value;
        if (val.length < 2) {
            datalist.innerHTML = '';
            return;
        }
        fetch(`/autocomplete?q=${encodeURIComponent(val)}`)
            .then(response => {
                if (!response.ok) throw new Error('Network response was not ok');
                return response.json();
            })
            .then(data => {
                datalist.innerHTML = '';
                data.forEach(item => {
                    const option = document.createElement('option');
                    option.value = item.name;
                    option.setAttribute('data-nzbn', item.nzbn);
                    datalist.appendChild(option);
                });
            })
            .catch(error => {
                console.error('Autocomplete error:', error);
                datalist.innerHTML = '';
            });
    });
});
</script>
</body>
</html>
"""



def format_director_name(first, last):
    return f"{first} {last}"

@app.route('/autocomplete')
def autocomplete():
    query = request.args.get('q', '').strip()
    suggestions = []
    if query:
        headers = {
            'Ocp-Apim-Subscription-Key': API_KEY,
            'Accept': 'application/json'
        }
        params = {
            'search-term': query,
            'page-size': 10
        }
        resp = requests.get(NZBN_SEARCH_URL, headers=headers, params=params, timeout=5)
        if resp.ok:
            data = resp.json()
            for item in data.get('items', []):
                name = item.get('entityName', '')
                nzbn = item.get('nzbn', '')
                if name and nzbn:
                    suggestions.append({'name': name, 'nzbn': nzbn})

    return jsonify(suggestions)

@app.route('/', methods=['GET', 'POST'])
def index():
    directors = None
    company_display_name = None
    error = None
    if request.method == 'POST':
        company_name = request.form['company_name'].strip()
        headers = {
            'Ocp-Apim-Subscription-Key': API_KEY,
            'Accept': 'application/json'
        }
        params = {
            'search-term': company_name,
            'page-size': 5
        }
        try:
            resp = requests.get(NZBN_SEARCH_URL, headers=headers, params=params, timeout=10)
            if resp.ok:
                data = resp.json()
                # Find the best match for the company name
                nzbn = None
                company_display_name = None
                for item in data.get('items', []):
                    if item.get('entityName', '').strip().lower() == company_name.lower():
                        nzbn = item.get('nzbn')
                        company_display_name = item.get('entityName', '')
                        break
                if not nzbn and data.get('items'):
                    # fallback: pick the first result
                    nzbn = data['items'][0].get('nzbn')
                    company_display_name = data['items'][0].get('entityName', '')
                if nzbn:
                    entity_resp = requests.get(NZBN_ENTITY_URL.format(nzbn), headers=headers, timeout=10)
                    if entity_resp.ok:
                        entity_data = entity_resp.json()
                        directors = []
                        roles = entity_data.get('roles', [])
                        for role in roles:
                            if role.get('roleType') == 'Director' and role.get("roleStatus") == 'ACTIVE':
                                person = role.get('rolePerson', {})
                                name_parts = [person.get('firstName', ''), person.get('lastName', '')]
                                full_name = ' '.join(filter(None, name_parts))
                                if full_name.strip():
                                    directors.append(full_name)
                        print(entity_data)
                        if not directors:
                            directors = []
                    else:
                        error = f"Failed to get entity details: {entity_resp.status_code} {entity_resp.reason}"

                else:
                    error = "No company found with that name."
            else:
                error = f"API error: {resp.status_code} {resp.reason}"
        except Exception as e:
            error = f"Request failed: {e}"
    return render_template_string(HTML_FORM, directors=directors, error=error, company_display_name=company_display_name)

if __name__ == '__main__':
    app.run(debug=True)

