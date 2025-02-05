import pytesseract
from pdf2image import convert_from_path
import cv2
import numpy as np
from PIL import Image
import torch
from transformers import LayoutLMv3Processor, LayoutLMv3ForTokenClassification
from typing import Dict, Any, List, Tuple
import logging
from dataclasses import dataclass

@dataclass
class OCRResult:
    text: str
    confidence: float
    bounding_box: Tuple[int, int, int, int]
    page_number: int

class OCRProcessor:
    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.confidence_threshold = config.get('OCR_CONFIDENCE_THRESHOLD', 0.85)
        self.layout_processor = LayoutLMv3Processor.from_pretrained("microsoft/layoutlmv3-base")
        self.layout_model = LayoutLMv3ForTokenClassification.from_pretrained("microsoft/layoutlmv3-base")
        
    async def process_document(self, file_path: str) -> List[OCRResult]:
        """Process document with OCR and layout analysis"""
        try:
            # Convert document to images
            images = self._convert_to_images(file_path)
            results = []
            
            for page_num, image in enumerate(images, 1):
                # Preprocess image
                processed_image = self._preprocess_image(image)
                
                # Perform OCR
                ocr_results = self._perform_ocr(processed_image)
                
                # Analyze layout
                layout_results = self._analyze_layout(processed_image, ocr_results)
                
                # Combine results
                for text, conf, bbox in zip(
                    layout_results['text'],
                    layout_results['confidence'],
                    layout_results['boxes']
                ):
                    if conf >= self.confidence_threshold:
                        results.append(OCRResult(
                            text=text,
                            confidence=conf,
                            bounding_box=bbox,
                            page_number=page_num
                        ))
            
            return results
            
        except Exception as e:
            self.logger.error(f"OCR processing failed: {str(e)}")
            raise
    
    def _convert_to_images(self, file_path: str) -> List[Image.Image]:
        """Convert document to list of images"""
        if file_path.lower().endswith('.pdf'):
            return convert_from_path(file_path)
        else:
            return [Image.open(file_path)]
    
    def _preprocess_image(self, image: Image.Image) -> np.ndarray:
        """Preprocess image for better OCR results"""
        # Convert to numpy array
        img_array = np.array(image)
        
        # Convert to grayscale
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        
        # Apply adaptive thresholding
        binary = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )
        
        # Denoise
        denoised = cv2.fastNlMeansDenoising(binary)
        
        # Deskew if needed
        angle = self._get_skew_angle(denoised)
        if abs(angle) > 0.5:
            denoised = self._rotate_image(denoised, angle)
        
        return denoised
    
    def _get_skew_angle(self, image: np.ndarray) -> float:
        """Detect skew angle of the image"""
        coords = np.column_stack(np.where(image > 0))
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = 90 + angle
        return angle
    
    def _rotate_image(self, image: np.ndarray, angle: float) -> np.ndarray:
        """Rotate image by given angle"""
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(
            image, M, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE
        )
        return rotated
    
    def _perform_ocr(self, image: np.ndarray) -> Dict[str, Any]:
        """Perform OCR with Tesseract"""
        return pytesseract.image_to_data(
            image,
            output_type=pytesseract.Output.DICT,
            config='--oem 3 --psm 6'
        )
    
    def _analyze_layout(
        self,
        image: np.ndarray,
        ocr_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze document layout using LayoutLMv3"""
        # Convert image to PIL
        pil_image = Image.fromarray(image)
        
        # Prepare inputs for layout model
        encoding = self.layout_processor(
            pil_image,
            return_tensors="pt",
            truncation=True
        )
        
        # Get layout predictions
        with torch.no_grad():
            outputs = self.layout_model(**encoding)
        
        # Process predictions
        predictions = outputs.logits.argmax(-1).squeeze().tolist()
        
        return {
            'text': ocr_results['text'],
            'confidence': ocr_results['conf'],
            'boxes': list(zip(
                ocr_results['left'],
                ocr_results['top'],
                ocr_results['width'],
                ocr_results['height']
            )),
            'layout': predictions
        } 