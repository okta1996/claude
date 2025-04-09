import os
import sys
import json
import base64
import requests
from PIL import Image
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QLineEdit, QTextEdit, QFileDialog, 
                             QTabWidget, QGridLayout, QMessageBox, QProgressBar, QComboBox)
from PyQt6.QtGui import QPixmap, QIcon, QFont
from PyQt6.QtCore import Qt, QThread, pyqtSignal

class GeminiThread(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    progress = pyqtSignal(int)
    
    def __init__(self, api_key, file_path, file_type):
        super().__init__()
        self.api_key = api_key
        self.file_path = file_path
        self.file_type = file_type
        
    def run(self):
        try:
            self.progress.emit(25)
            
            # Read file as binary
            with open(self.file_path, 'rb') as file:
                file_bytes = file.read()
            
            self.progress.emit(50)
            
            # Convert to base64
            file_b64 = base64.b64encode(file_bytes).decode('utf-8')
            
            # Define appropriate prompt based on file type
            if self.file_type == "image":
                prompt = "Generate comprehensive metadata for this image including a descriptive title, detailed description, and relevant keywords. Format the response as JSON with fields 'title', 'description', and 'keywords' (as an array)."
                mime_type = "image/jpeg"  # Adjust based on actual file type if needed
            else:  # video
                prompt = "Generate comprehensive metadata for this video including a descriptive title, detailed description, and relevant keywords. Format the response as JSON with fields 'title', 'description', and 'keywords' (as an array)."
                mime_type = "video/mp4"  # Adjust based on actual file type if needed
            
            # Prepare the API request to Gemini 1.5 Flash
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}"
            
            # Prepare request payload for Gemini 1.5 Flash
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt},
                            {
                                "inline_data": {
                                    "mime_type": mime_type,
                                    "data": file_b64
                                }
                            }
                        ]
                    }
                ],
                "generation_config": {
                    "temperature": 0.4,
                    "top_p": 0.95,
                    "top_k": 40
                }
            }
            
            headers = {
                "Content-Type": "application/json"
            }
            
            self.progress.emit(75)
            
            # Make the API request
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code != 200:
                try:
                    error_data = response.json()
                    error_message = error_data.get('error', {}).get('message', f"HTTP Error: {response.status_code}")
                    if 'details' in error_data.get('error', {}):
                        details = error_data['error']['details']
                        if details:
                            error_message += f"\nDetails: {details}"
                except:
                    error_message = f"HTTP Error: {response.status_code}"
                self.error.emit(f"API Error: {error_message}")
                return
            
            # Parse the response
            try:
                response_data = response.json()
                
                # Extract the content from Gemini's response structure
                if 'candidates' in response_data and len(response_data['candidates']) > 0:
                    text_content = response_data['candidates'][0]['content']['parts'][0]['text']
                else:
                    self.error.emit("No valid response from Gemini API")
                    return
                
                # Try to parse the JSON from the response
                try:
                    # First check if the response is already valid JSON (unlikely)
                    metadata = json.loads(text_content)
                except json.JSONDecodeError:
                    # If not valid JSON, try to extract JSON from markdown code blocks
                    import re
                    json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', text_content, re.DOTALL)
                    
                    if json_match:
                        try:
                            metadata = json.loads(json_match.group(1))
                        except json.JSONDecodeError:
                            # If that fails, try to parse the structure manually
                            metadata = self._extract_metadata_manually(text_content)
                    else:
                        # If no code blocks, try to parse the structure manually
                        metadata = self._extract_metadata_manually(text_content)
                
                self.progress.emit(100)
                self.finished.emit(metadata)
                
            except Exception as e:
                self.error.emit(f"Failed to parse API response: {str(e)}")
        
        except Exception as e:
            self.error.emit(f"Error: {str(e)}")
    
    def _extract_metadata_manually(self, text):
        """Extract metadata manually from text response when JSON parsing fails"""
        metadata = {
            'title': '',
            'description': '',
            'keywords': []
        }
        
        # Try to extract title
        import re
        title_patterns = [
            r'(?:Title|TITLE):\s*(.*?)(?:\n|$)',
            r'"title":\s*"(.*?)"',
            r'title.*?["\s:]+([^"\n]+)["\s]'
        ]
        
        for pattern in title_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                metadata['title'] = match.group(1).strip()
                break
        
        # Try to extract description
        desc_match = re.search(r'(?:Description|DESCRIPTION):\s*(.*?)(?:\n\s*\n|\n\s*Keywords|\n\s*$)', 
                              text, re.IGNORECASE | re.DOTALL)
        if desc_match:
            metadata['description'] = desc_match.group(1).strip()
        
        # Try to extract keywords
        keywords_patterns = [
            r'(?:Keywords|KEYWORDS):\s*(.*?)(?:\n\s*\n|\n\s*$)',
            r'"keywords":\s*\[(.*?)\]',
            r'keywords.*?["\s:]+([^"\n]+)["\s]'
        ]
        
        for pattern in keywords_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                keywords_text = match.group(1).strip()
                # Handle different formats of keywords
                if ',' in keywords_text:
                    # Comma-separated list
                    keywords = [k.strip().strip('"\'') for k in keywords_text.split(',')]
                elif '"' in keywords_text:
                    # JSON-like array with quotes
                    keywords = re.findall(r'"([^"]+)"', keywords_text)
                else:
                    # Space-separated or other format
                    keywords = [k.strip() for k in keywords_text.split()]
                
                metadata['keywords'] = keywords
                break
        
        return metadata


class MetadataGeneratorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Metadata Generator - Gemini 1.5 Flash")
        self.setGeometry(100, 100, 1000, 800)
        self.setup_ui()
        
        # Store the current file path
        self.current_file_path = None
        self.current_file_type = None
        
    def setup_ui(self):
        # Main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        
        # Title and version
        title_layout = QHBoxLayout()
        title_label = QLabel("Metadata Generator")
        title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        version_label = QLabel("v1.1 - Powered by Gemini 1.5 Flash")
        version_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        title_layout.addWidget(title_label)
        title_layout.addWidget(version_label)
        
        # API Key section
        api_key_layout = QHBoxLayout()
        api_key_label = QLabel("Gemini API Key:")
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Enter your Gemini AI API key...")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        load_key_button = QPushButton("Load from File")
        load_key_button.clicked.connect(self.load_api_key)
        
        save_key_button = QPushButton("Save Key")
        save_key_button.clicked.connect(self.save_api_key)
        
        api_key_layout.addWidget(api_key_label)
        api_key_layout.addWidget(self.api_key_input)
        api_key_layout.addWidget(load_key_button)
        api_key_layout.addWidget(save_key_button)
        
        # Model selection section
        model_layout = QHBoxLayout()
        model_label = QLabel("Model:")
        self.model_combo = QComboBox()
        self.model_combo.addItems(["gemini-1.5-flash"])
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.model_combo)
        model_layout.addStretch()
        
        # File selection section
        file_section_layout = QHBoxLayout()
        
        # File type selection
        file_type_layout = QVBoxLayout()
        file_type_label = QLabel("File Type:")
        self.file_type_combo = QComboBox()
        self.file_type_combo.addItems(["Image", "Video"])
        file_type_layout.addWidget(file_type_label)
        file_type_layout.addWidget(self.file_type_combo)
        
        # File browser
        self.file_path_input = QLineEdit()
        self.file_path_input.setPlaceholderText("Select a file...")
        
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self.browse_file)
        
        file_browser_layout = QHBoxLayout()
        file_browser_layout.addWidget(self.file_path_input)
        file_browser_layout.addWidget(browse_button)
        
        file_section_layout.addLayout(file_type_layout)
        file_section_layout.addLayout(file_browser_layout)
        
        # Preview section
        preview_layout = QVBoxLayout()
        preview_label = QLabel("Preview:")
        self.preview_image = QLabel()
        self.preview_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_image.setFixedHeight(300)
        self.preview_image.setStyleSheet("border: 1px solid #ccc; background-color: #f5f5f5;")
        
        preview_layout.addWidget(preview_label)
        preview_layout.addWidget(self.preview_image)
        
        # Generate section
        generate_layout = QHBoxLayout()
        self.generate_button = QPushButton("Generate Metadata")
        self.generate_button.setFixedHeight(50)
        self.generate_button.clicked.connect(self.generate_metadata)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        
        generate_layout.addWidget(self.generate_button)
        generate_layout.addWidget(self.progress_bar)
        
        # Results section
        results_tabs = QTabWidget()
        
        # Title tab
        title_widget = QWidget()
        title_layout = QVBoxLayout()
        title_label = QLabel("Title:")
        self.title_input = QTextEdit()
        title_layout.addWidget(title_label)
        title_layout.addWidget(self.title_input)
        title_widget.setLayout(title_layout)
        
        # Description tab
        desc_widget = QWidget()
        desc_layout = QVBoxLayout()
        desc_label = QLabel("Description:")
        self.desc_input = QTextEdit()
        desc_layout.addWidget(desc_label)
        desc_layout.addWidget(self.desc_input)
        desc_widget.setLayout(desc_layout)
        
        # Keywords tab
        keywords_widget = QWidget()
        keywords_layout = QVBoxLayout()
        keywords_label = QLabel("Keywords (comma-separated):")
        self.keywords_input = QTextEdit()
        keywords_layout.addWidget(keywords_label)
        keywords_layout.addWidget(self.keywords_input)
        keywords_widget.setLayout(keywords_layout)
        
        results_tabs.addTab(title_widget, "Title")
        results_tabs.addTab(desc_widget, "Description")
        results_tabs.addTab(keywords_widget, "Keywords")
        
        # Export section
        export_layout = QHBoxLayout()
        self.export_button = QPushButton("Export Metadata")
        self.export_button.setFixedHeight(40)
        self.export_button.clicked.connect(self.export_metadata)
        
        apply_button = QPushButton("Apply to File")
        apply_button.setFixedHeight(40)
        apply_button.clicked.connect(self.apply_to_file)
        
        export_layout.addWidget(self.export_button)
        export_layout.addWidget(apply_button)
        
        # Add all sections to main layout
        main_layout.addLayout(title_layout)
        main_layout.addLayout(api_key_layout)
        main_layout.addLayout(model_layout)
        main_layout.addLayout(file_section_layout)
        main_layout.addLayout(preview_layout)
        main_layout.addLayout(generate_layout)
        main_layout.addWidget(results_tabs)
        main_layout.addLayout(export_layout)
        
        # Set the main layout
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
    
    def load_api_key(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select API Key File", "", "Text Files (*.txt)")
        if file_path:
            try:
                with open(file_path, 'r') as file:
                    api_key = file.read().strip()
                    self.api_key_input.setText(api_key)
                    QMessageBox.information(self, "Success", "API Key loaded successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load API key: {str(e)}")
    
    def save_api_key(self):
        api_key = self.api_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "Warning", "Please enter an API key first.")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(self, "Save API Key", "", "Text Files (*.txt)")
        if file_path:
            try:
                with open(file_path, 'w') as file:
                    file.write(api_key)
                QMessageBox.information(self, "Success", "API Key saved successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save API key: {str(e)}")
    
    def browse_file(self):
        file_type = self.file_type_combo.currentText().lower()
        
        if file_type == "image":
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Select Image", "", "Image Files (*.png *.jpg *.jpeg *.bmp *.gif)"
            )
        else:  # video
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Select Video", "", "Video Files (*.mp4 *.avi *.mov *.mkv)"
            )
            
        if file_path:
            self.file_path_input.setText(file_path)
            self.current_file_path = file_path
            self.current_file_type = file_type
            self.update_preview()
    
    def update_preview(self):
        if not self.current_file_path:
            return
        
        if self.current_file_type == "image":
            try:
                pixmap = QPixmap(self.current_file_path)
                if not pixmap.isNull():
                    pixmap = pixmap.scaled(
                        self.preview_image.width(), self.preview_image.height(),
                        Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                    )
                    self.preview_image.setPixmap(pixmap)
                else:
                    self.preview_image.setText("Unable to load image preview")
            except Exception as e:
                self.preview_image.setText(f"Preview error: {str(e)}")
        else:  # video
            # Display a placeholder for video files
            self.preview_image.setText(f"Video file selected: {os.path.basename(self.current_file_path)}")
    
    def generate_metadata(self):
        api_key = self.api_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "Warning", "Please enter your Gemini API key.")
            return
        
        if not self.current_file_path:
            QMessageBox.warning(self, "Warning", "Please select a file first.")
            return
        
        # Reset progress bar
        self.progress_bar.setValue(0)
        
        # Disable the generate button while processing
        self.generate_button.setEnabled(False)
        self.generate_button.setText("Generating...")
        
        # Create and start the processing thread
        self.thread = GeminiThread(api_key, self.current_file_path, self.current_file_type)
        self.thread.finished.connect(self.metadata_received)
        self.thread.error.connect(self.show_error)
        self.thread.progress.connect(self.update_progress)
        self.thread.start()
    
    def update_progress(self, value):
        self.progress_bar.setValue(value)
    
    def metadata_received(self, metadata):
        # Update the UI with the received metadata
        self.title_input.setText(metadata.get('title', ''))
        self.desc_input.setText(metadata.get('description', ''))
        
        keywords = metadata.get('keywords', [])
        if isinstance(keywords, list):
            self.keywords_input.setText(', '.join(keywords))
        else:
            self.keywords_input.setText(str(keywords))
        
        # Re-enable the generate button
        self.generate_button.setEnabled(True)
        self.generate_button.setText("Generate Metadata")
        
        # Complete the progress bar
        self.progress_bar.setValue(100)
        
        QMessageBox.information(self, "Success", "Metadata generated successfully!")
    
    def show_error(self, error_message):
        QMessageBox.critical(self, "Error", error_message)
        self.generate_button.setEnabled(True)
        self.generate_button.setText("Generate Metadata")
        self.progress_bar.setValue(0)
    
    def export_metadata(self):
        if not self.title_input.toPlainText().strip():
            QMessageBox.warning(self, "Warning", "No metadata to export. Generate metadata first.")
            return
        
        # Create metadata dictionary
        metadata = {
            "title": self.title_input.toPlainText().strip(),
            "description": self.desc_input.toPlainText().strip(),
            "keywords": [k.strip() for k in self.keywords_input.toPlainText().split(',') if k.strip()],
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source_file": self.current_file_path if self.current_file_path else "Unknown"
        }
        
        # Export to file
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Metadata", "", "JSON Files (*.json);;Text Files (*.txt)"
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'w') as file:
                if file_path.endswith('.json'):
                    json.dump(metadata, file, indent=4)
                else:
                    file.write(f"Title: {metadata['title']}\n\n")
                    file.write(f"Description: {metadata['description']}\n\n")
                    file.write(f"Keywords: {', '.join(metadata['keywords'])}\n\n")
                    file.write(f"Generated at: {metadata['generated_at']}\n")
                    file.write(f"Source file: {metadata['source_file']}\n")
                    
            QMessageBox.information(self, "Success", f"Metadata exported successfully to {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export metadata: {str(e)}")
    
    def apply_to_file(self):
        # This function would apply the metadata directly to the file
        # This requires specific libraries for different file types
        
        QMessageBox.information(
            self, 
            "Feature not implemented",
            "This feature would apply metadata directly to the file. "
            "It requires additional libraries specific to each file format."
        )

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Use Fusion style for better cross-platform look
    
    # Set application stylesheet for better aesthetics
    app.setStyleSheet("""
        QMainWindow {
            background-color: #f5f5f5;
        }
        QLabel {
            font-weight: bold;
        }
        QPushButton {
            background-color: #0078d7;
            color: white;
            border-radius: 4px;
            padding: 6px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #1a88e0;
        }
        QPushButton:disabled {
            background-color: #cccccc;
        }
        QTextEdit, QLineEdit {
            border: 1px solid #aaa;
            border-radius: 4px;
            padding: 5px;
            background-color: white;
        }
        QTabWidget::pane {
            border: 1px solid #aaa;
            background-color: white;
        }
        QTabBar::tab {
            background-color: #e1e1e1;
            border: 1px solid #aaa;
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            padding: 5px 10px;
        }
        QTabBar::tab:selected {
            background-color: white;
        }
    """)
    
    window = MetadataGeneratorApp()
    window.show()
    
    sys.exit(app.exec())