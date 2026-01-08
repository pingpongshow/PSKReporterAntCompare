#!/usr/bin/env python3
"""
ADIF Antenna Comparison Tool
Docker version with web interface on port 5995
"""

import re
import os
from flask import Flask, render_template_string, request, jsonify
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Dict, Optional
import io
import base64

app = Flask(__name__)

@dataclass
class ADIFRecord:
    """Represents a single ADIF record"""
    freq: float
    call: str
    operator: str
    gridsquare: str
    snr: Optional[float]
    distance: Optional[float]
    antenna_id: str
    
    @property
    def band(self) -> str:
        """Determine band from frequency"""
        freq_mhz = self.freq
        if 7.0 <= freq_mhz < 7.3:
            return "40m"
        elif 10.1 <= freq_mhz < 10.15:
            return "30m"
        elif 14.0 <= freq_mhz < 14.35:
            return "20m"
        elif 18.068 <= freq_mhz < 18.168:
            return "17m"
        elif 21.0 <= freq_mhz < 21.45:
            return "15m"
        elif 24.89 <= freq_mhz < 24.99:
            return "12m"
        elif 28.0 <= freq_mhz < 29.7:
            return "10m"
        else:
            return f"{freq_mhz:.3f}MHz"
    
    @property
    def gridsquare_6(self) -> str:
        """Return 6-character gridsquare"""
        return self.gridsquare[:6] if len(self.gridsquare) >= 6 else self.gridsquare


class ADIFParser:
    """Parse ADIF files"""
    
    @staticmethod
    def parse_file(filepath: str) -> List[ADIFRecord]:
        """Parse an ADIF file and return list of records"""
        records = []
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            record_pattern = r'<eor>'
            raw_records = content.split(record_pattern)
            
            for raw_record in raw_records:
                if not raw_record.strip():
                    continue
                
                record = ADIFParser._parse_record(raw_record)
                if record:
                    records.append(record)
        
        except Exception as e:
            print(f"Error parsing file {filepath}: {e}")
        
        return records
    
    @staticmethod
    def _parse_record(raw_record: str) -> Optional[ADIFRecord]:
        """Parse a single ADIF record"""
        def get_field(field_name: str, record: str) -> Optional[str]:
            pattern = rf'<{field_name}:\d+(?::\w+)?>(.*?)<'
            match = re.search(pattern, record, re.IGNORECASE)
            return match.group(1).strip() if match else None
        
        try:
            freq_str = get_field('FREQ', raw_record)
            call = get_field('CALL', raw_record)
            operator = get_field('OPERATOR', raw_record)
            gridsquare = get_field('GRIDSQUARE', raw_record) or get_field('MY_GRIDSQUARE', raw_record)
            snr_str = get_field('APP_PSKREP_SNR', raw_record)
            distance_str = get_field('DISTANCE', raw_record)
            
            if not freq_str or not call:
                return None
            
            freq = float(freq_str)
            snr = float(snr_str) if snr_str else None
            distance = float(distance_str) if distance_str else None
            
            if snr is None and distance is None:
                return None
            
            antenna_match = re.search(r'/(\d+)', call)
            antenna_id = antenna_match.group(1) if antenna_match else "unknown"
            
            return ADIFRecord(
                freq=freq,
                call=call,
                operator=operator or "",
                gridsquare=gridsquare or "",
                snr=snr,
                distance=distance,
                antenna_id=antenna_id
            )
        
        except Exception as e:
            print(f"Error parsing record: {e}")
            return None


class AntennaAnalyzer:
    """Analyze antenna performance"""
    
    def __init__(self, records_dict: Dict[str, List[ADIFRecord]], mode: str):
        self.records = records_dict
        self.mode = mode
        self.band_data = None
    
    def analyze(self):
        """Perform analysis based on mode"""
        self.band_data = defaultdict(lambda: defaultdict(list))
        
        if self.mode == "transmission":
            self._analyze_transmission()
        else:
            self._analyze_reception()
        
        return self.band_data
    
    def _analyze_transmission(self):
        """Analyze transmission efficiency"""
        for antenna_id, records in self.records.items():
            for record in records:
                if record.operator:
                    key = (record.operator, record.gridsquare_6)
                    self.band_data[record.band][key].append((antenna_id, record))
    
    def _analyze_reception(self):
        """Analyze reception efficiency"""
        for antenna_id, records in self.records.items():
            for record in records:
                key = (record.call, record.gridsquare_6)
                self.band_data[record.band][key].append((antenna_id, record))
    
    def generate_band_comparison(self):
        """Generate band comparison charts"""
        bands = sorted(self.band_data.keys(), key=self._band_sort_key)
        
        if not bands:
            return None
        
        num_bands = len(bands)
        rows = (num_bands + 2) // 3
        cols = min(3, num_bands)
        
        fig, axes = plt.subplots(rows, cols, figsize=(15, 5 * rows))
        if num_bands == 1:
            axes = [axes]
        else:
            axes = axes.flatten()
        
        for idx, band in enumerate(bands):
            self._plot_band_data(axes[idx], band, self.band_data[band])
        
        for idx in range(len(bands), len(axes)):
            axes[idx].axis('off')
        
        plt.tight_layout()
        return self._fig_to_base64(fig)
    
    def _plot_band_data(self, ax, band, station_data):
        """Plot comparison data for a single band"""
        antenna_snrs = defaultdict(list)
        
        for station_key, records_list in station_data.items():
            if len(records_list) > 1:
                for antenna_id, record in records_list:
                    if record.snr is not None:
                        antenna_snrs[antenna_id].append(record.snr)
        
        if not antenna_snrs:
            ax.text(0.5, 0.5, f'{band}\nNo comparable data', 
                   ha='center', va='center', transform=ax.transAxes, fontsize=12)
            ax.set_xticks([])
            ax.set_yticks([])
            return
        
        antenna_ids = sorted(antenna_snrs.keys())
        data = [antenna_snrs[aid] for aid in antenna_ids]
        labels = [f'/{aid}' for aid in antenna_ids]
        
        bp = ax.boxplot(data, labels=labels, patch_artist=True)
        
        colors = plt.cm.Set3(np.linspace(0, 1, len(antenna_ids)))
        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
        
        ax.set_xlabel('Antenna', fontsize=10)
        ax.set_ylabel('SNR (dB)', fontsize=10)
        ax.set_title(f'{band} - SNR Comparison', fontsize=11, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.axhline(y=0, color='r', linestyle='--', alpha=0.5, linewidth=1)
    
    def generate_overall_ranking(self):
        """Generate overall ranking charts"""
        antenna_band_avg = defaultdict(lambda: defaultdict(list))
        antenna_overall = defaultdict(list)
        
        for band, station_data in self.band_data.items():
            for station_key, records_list in station_data.items():
                for antenna_id, record in records_list:
                    if record.snr is not None:
                        antenna_band_avg[antenna_id][band].append(record.snr)
                        antenna_overall[antenna_id].append(record.snr)
        
        if not antenna_overall:
            return None
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
        
        antenna_ids = sorted(antenna_band_avg.keys())
        bands = sorted(set(b for ant_data in antenna_band_avg.values() for b in ant_data.keys()),
                      key=self._band_sort_key)
        
        x = np.arange(len(bands))
        width = 0.8 / len(antenna_ids) if antenna_ids else 0.8
        
        colors = plt.cm.Set3(np.linspace(0, 1, len(antenna_ids)))
        
        for idx, (antenna_id, color) in enumerate(zip(antenna_ids, colors)):
            avgs = [np.mean(antenna_band_avg[antenna_id].get(band, [np.nan])) 
                   for band in bands]
            offset = (idx - len(antenna_ids)/2) * width + width/2
            ax1.bar(x + offset, avgs, width, label=f'Antenna /{antenna_id}', color=color)
        
        ax1.set_xlabel('Band', fontsize=11)
        ax1.set_ylabel('Average SNR (dB)', fontsize=11)
        ax1.set_title('Average SNR by Band and Antenna', fontsize=13, fontweight='bold')
        ax1.set_xticks(x)
        ax1.set_xticklabels(bands)
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        ax1.axhline(y=0, color='r', linestyle='--', alpha=0.5)
        
        antenna_ids_sorted = sorted(antenna_overall.keys(), 
                                   key=lambda x: np.mean(antenna_overall[x]), 
                                   reverse=True)
        avgs = [np.mean(antenna_overall[aid]) for aid in antenna_ids_sorted]
        stds = [np.std(antenna_overall[aid]) for aid in antenna_ids_sorted]
        
        bar_colors = plt.cm.RdYlGn([(a + 30) / 60 for a in avgs])
        bars = ax2.bar(range(len(antenna_ids_sorted)), avgs, color=bar_colors, 
                      yerr=stds, capsize=5, alpha=0.8)
        
        ax2.set_xlabel('Antenna', fontsize=11)
        ax2.set_ylabel('Overall Average SNR (dB)', fontsize=11)
        ax2.set_title('Overall Antenna Performance Ranking', fontsize=13, fontweight='bold')
        ax2.set_xticks(range(len(antenna_ids_sorted)))
        ax2.set_xticklabels([f'/{aid}' for aid in antenna_ids_sorted])
        ax2.grid(True, alpha=0.3)
        ax2.axhline(y=0, color='r', linestyle='--', alpha=0.5)
        
        for bar, avg in zip(bars, avgs):
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{avg:.1f}', ha='center', va='bottom', fontsize=9)
        
        plt.tight_layout()
        return self._fig_to_base64(fig)
    
    def generate_distance_analysis(self):
        """Generate distance vs SNR analysis"""
        antenna_data = defaultdict(lambda: {'distances': [], 'snrs': []})
        
        for band, station_data in self.band_data.items():
            for station_key, records_list in station_data.items():
                for antenna_id, record in records_list:
                    if record.snr is not None and record.distance is not None:
                        antenna_data[antenna_id]['distances'].append(record.distance)
                        antenna_data[antenna_id]['snrs'].append(record.snr)
        
        if not antenna_data:
            return None
        
        fig, ax = plt.subplots(figsize=(12, 7))
        
        antenna_ids = sorted(antenna_data.keys())
        colors = plt.cm.Set3(np.linspace(0, 1, len(antenna_ids)))
        
        for antenna_id, color in zip(antenna_ids, colors):
            data = antenna_data[antenna_id]
            ax.scatter(data['distances'], data['snrs'], 
                      label=f'Antenna /{antenna_id}', 
                      alpha=0.6, s=40, color=color, edgecolors='black', linewidth=0.5)
        
        ax.set_xlabel('Distance (km)', fontsize=11)
        ax.set_ylabel('SNR (dB)', fontsize=11)
        ax.set_title('Signal Strength vs Distance', fontsize=13, fontweight='bold')
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)
        ax.axhline(y=0, color='r', linestyle='--', alpha=0.5)
        
        plt.tight_layout()
        return self._fig_to_base64(fig)
    
    @staticmethod
    def _fig_to_base64(fig):
        """Convert matplotlib figure to base64 string"""
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)
        return img_base64
    
    @staticmethod
    def _band_sort_key(band: str) -> float:
        """Sort key for bands"""
        band_order = {"40m": 40, "30m": 30, "20m": 20, "17m": 17, "15m": 15, "12m": 12, "10m": 10}
        return band_order.get(band, 999)


HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>ADIF Antenna Comparison Tool</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .header p { font-size: 1.1em; opacity: 0.9; }
        .controls {
            padding: 30px;
            background: #f8f9fa;
            border-bottom: 2px solid #e9ecef;
        }
        .control-group {
            margin-bottom: 20px;
        }
        .control-group label {
            display: block;
            font-weight: 600;
            margin-bottom: 8px;
            color: #495057;
        }
        .radio-group {
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
        }
        .radio-group label {
            display: flex;
            align-items: center;
            cursor: pointer;
            font-weight: normal;
        }
        .radio-group input[type="radio"] {
            margin-right: 8px;
        }
        input[type="file"] {
            display: block;
            width: 100%;
            padding: 12px;
            border: 2px dashed #667eea;
            border-radius: 8px;
            background: white;
            cursor: pointer;
            font-size: 1em;
        }
        button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 14px 30px;
            font-size: 1.1em;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            transition: transform 0.2s, box-shadow 0.2s;
            margin-right: 10px;
        }
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.4);
        }
        button:disabled {
            background: #adb5bd;
            cursor: not-allowed;
            transform: none;
        }
        .file-list {
            padding: 20px 30px;
            background: white;
        }
        .file-item {
            padding: 10px 15px;
            background: #e7f3ff;
            border-left: 4px solid #667eea;
            margin-bottom: 8px;
            border-radius: 4px;
            font-size: 0.95em;
        }
        .results {
            padding: 30px;
        }
        .tabs {
            display: flex;
            border-bottom: 2px solid #e9ecef;
            margin-bottom: 20px;
        }
        .tab {
            padding: 15px 25px;
            cursor: pointer;
            border: none;
            background: none;
            font-size: 1em;
            font-weight: 600;
            color: #6c757d;
            border-bottom: 3px solid transparent;
            transition: all 0.3s;
            margin-right: 5px;
        }
        .tab:hover { color: #667eea; }
        .tab.active {
            color: #667eea;
            border-bottom-color: #667eea;
        }
        .tab-content {
            display: none;
        }
        .tab-content.active {
            display: block;
            animation: fadeIn 0.3s;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .chart-container {
            text-align: center;
            margin: 20px 0;
        }
        .chart-container img {
            max-width: 100%;
            height: auto;
            border-radius: 8px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }
        .loading {
            text-align: center;
            padding: 50px;
            font-size: 1.2em;
            color: #667eea;
        }
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 50px;
            height: 50px;
            animation: spin 1s linear infinite;
            margin: 20px auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .error {
            background: #f8d7da;
            color: #721c24;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #dc3545;
            margin: 20px 0;
        }
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #6c757d;
        }
        .empty-state h3 { margin-bottom: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📡 ADIF Antenna Comparison Tool</h1>
            <p>Compare antenna performance across multiple bands using PSKreporter data</p>
        </div>
        
        <div class="controls">
            <div class="control-group">
                <label>Analysis Mode:</label>
                <div class="radio-group">
                    <label>
                        <input type="radio" name="mode" value="transmission" checked>
                        Transmission (My Beacon)
                    </label>
                    <label>
                        <input type="radio" name="mode" value="reception">
                        Reception (Signals I Received)
                    </label>
                </div>
            </div>
            
            <div class="control-group">
                <label>Select ADIF Files (up to 10):</label>
                <input type="file" id="fileInput" multiple accept=".adif,.adi">
            </div>
            
            <div>
                <button onclick="analyzeFiles()" id="analyzeBtn" disabled>Analyze Antennas</button>
                <button onclick="clearAll()">Clear All</button>
            </div>
        </div>
        
        <div class="file-list" id="fileList"></div>
        
        <div class="results" id="results">
            <div class="empty-state">
                <h3>👆 Get Started</h3>
                <p>Load at least 2 ADIF files to begin comparing antenna performance</p>
            </div>
        </div>
    </div>
    
    <script>
        let uploadedFiles = [];
        
        document.getElementById('fileInput').addEventListener('change', function(e) {
            const files = Array.from(e.target.files);
            if (files.length > 10) {
                alert('Maximum 10 files allowed');
                return;
            }
            
            const fileList = document.getElementById('fileList');
            fileList.innerHTML = '<h3 style="margin-bottom:15px;">Loaded Files:</h3>';
            
            files.forEach((file, idx) => {
                const div = document.createElement('div');
                div.className = 'file-item';
                div.textContent = `${idx + 1}. ${file.name}`;
                fileList.appendChild(div);
            });
            
            uploadedFiles = files;
            document.getElementById('analyzeBtn').disabled = files.length < 2;
        });
        
        async function analyzeFiles() {
            if (uploadedFiles.length < 2) {
                alert('Please load at least 2 ADIF files');
                return;
            }
            
            const mode = document.querySelector('input[name="mode"]:checked').value;
            const formData = new FormData();
            
            uploadedFiles.forEach((file, idx) => {
                formData.append('files', file);
            });
            formData.append('mode', mode);
            
            const results = document.getElementById('results');
            results.innerHTML = '<div class="loading"><div class="spinner"></div><p>Analyzing antenna performance...</p></div>';
            
            try {
                const response = await fetch('/analyze', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (data.error) {
                    results.innerHTML = `<div class="error">${data.error}</div>`;
                    return;
                }
                
                displayResults(data);
            } catch (error) {
                results.innerHTML = `<div class="error">Error: ${error.message}</div>`;
            }
        }
        
        function displayResults(data) {
            const results = document.getElementById('results');
            
            let html = '<div class="tabs">';
            html += '<button class="tab active" onclick="showTab(0)">Band Comparison</button>';
            html += '<button class="tab" onclick="showTab(1)">Overall Ranking</button>';
            html += '<button class="tab" onclick="showTab(2)">Distance Analysis</button>';
            html += '</div>';
            
            html += '<div class="tab-content active">';
            if (data.band_comparison) {
                html += `<div class="chart-container"><img src="data:image/png;base64,${data.band_comparison}"></div>`;
            } else {
                html += '<div class="empty-state"><p>No band comparison data available</p></div>';
            }
            html += '</div>';
            
            html += '<div class="tab-content">';
            if (data.overall_ranking) {
                html += `<div class="chart-container"><img src="data:image/png;base64,${data.overall_ranking}"></div>`;
            } else {
                html += '<div class="empty-state"><p>No ranking data available</p></div>';
            }
            html += '</div>';
            
            html += '<div class="tab-content">';
            if (data.distance_analysis) {
                html += `<div class="chart-container"><img src="data:image/png;base64,${data.distance_analysis}"></div>`;
            } else {
                html += '<div class="empty-state"><p>No distance analysis data available</p></div>';
            }
            html += '</div>';
            
            results.innerHTML = html;
        }
        
        function showTab(index) {
            const tabs = document.querySelectorAll('.tab');
            const contents = document.querySelectorAll('.tab-content');
            
            tabs.forEach((tab, idx) => {
                tab.classList.toggle('active', idx === index);
            });
            
            contents.forEach((content, idx) => {
                content.classList.toggle('active', idx === index);
            });
        }
        
        function clearAll() {
            uploadedFiles = [];
            document.getElementById('fileInput').value = '';
            document.getElementById('fileList').innerHTML = '';
            document.getElementById('results').innerHTML = '<div class="empty-state"><h3>👆 Get Started</h3><p>Load at least 2 ADIF files to begin comparing antenna performance</p></div>';
            document.getElementById('analyzeBtn').disabled = true;
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        files = request.files.getlist('files')
        mode = request.form.get('mode', 'transmission')
        
        if len(files) < 2:
            return jsonify({'error': 'At least 2 files required'})
        
        records_dict = {}
        temp_dir = '/tmp/adif_analysis'
        os.makedirs(temp_dir, exist_ok=True)
        
        for file in files:
            filepath = os.path.join(temp_dir, file.filename)
            file.save(filepath)
            
            records = ADIFParser.parse_file(filepath)
            if records:
                antenna_ids = set(r.antenna_id for r in records)
                if len(antenna_ids) == 1:
                    antenna_id = list(antenna_ids)[0]
                    records_dict[antenna_id] = records
        
        if len(records_dict) < 2:
            return jsonify({'error': 'Need at least 2 valid antenna files'})
        
        analyzer = AntennaAnalyzer(records_dict, mode)
        analyzer.analyze()
        
        band_comparison = analyzer.generate_band_comparison()
        overall_ranking = analyzer.generate_overall_ranking()
        distance_analysis = analyzer.generate_distance_analysis()
        
        return jsonify({
            'band_comparison': band_comparison,
            'overall_ranking': overall_ranking,
            'distance_analysis': distance_analysis
        })
    
    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 ADIF Antenna Comparison Tool")
    print("="*60)
    print("\n📡 Starting web server on port 5995...")
    print("🌐 Open your browser to: http://localhost:5995")
    print("\n💡 Instructions:")
    print("   1. Select analysis mode (Transmission/Reception)")
    print("   2. Load your ADIF files (one per antenna)")
    print("   3. Click 'Analyze Antennas'")
    print("\n⌨️  Press Ctrl+C to stop the server\n")
    
    app.run(debug=False, host='0.0.0.0', port=5995)
