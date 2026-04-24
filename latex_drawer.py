import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np
from PIL import Image, ImageTk, ImageOps
import pyautogui
import time
import os
import cv2
import requests
from urllib.parse import quote

class LaTeXDrawer:
    def __init__(self, root):
        self.root = root
        self.root.title("LaTeX Drawer")
        self.root.geometry("1000x650")
        
        self.preview_image = None
        self.preview_pil_image = None
        self.drawing_strokes = []
        self.scale = tk.DoubleVar(value=1.0)
        self.draw_speed = tk.StringVar(value="fastest")
        self.sparsity = tk.IntVar(value=2)
        self.drawing = False
        self.offset_x = tk.IntVar(value=0)
        self.offset_y = tk.IntVar(value=0)
        
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0
        
        self.setup_ui()
        
    def setup_ui(self):
        main = ttk.Frame(self.root, padding="10")
        main.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Input
        input_frame = ttk.LabelFrame(main, text="LaTeX Input", padding="10")
        input_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        self.latex_text = tk.Text(input_frame, height=3, width=70, wrap=tk.WORD)
        self.latex_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        btn_frame = ttk.Frame(input_frame)
        btn_frame.pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Preview", command=self.generate_preview).pack(pady=2)
        ttk.Button(btn_frame, text="Clear", command=lambda: self.latex_text.delete('1.0', tk.END)).pack(pady=2)
        
        # Matrix examples only
        ex = ttk.Frame(input_frame)
        ex.pack(fill=tk.X, pady=5)
        
        matrices = [
            (r"\begin{bmatrix} 1 & 2 \\ 3 & 4 \end{bmatrix}", "2×2"),
            (r"\begin{bmatrix} a & b & c \\ d & e & f \\ g & h & i \end{bmatrix}", "3×3"),
            (r"\begin{pmatrix} x \\ y \\ z \end{pmatrix}", "Vec"),
            (r"\begin{vmatrix} a & b \\ c & d \end{vmatrix} = ad - bc", "Det"),
            (r"\left[\begin{array}{cc|c} 1 & 2 & 3 \\ 4 & 5 & 6 \end{array}\right]", "Aug"),
        ]
        
        for latex, name in matrices:
            ttk.Button(ex, text=name, command=lambda l=latex: self.set_latex(l)).pack(side=tk.LEFT, padx=2)
        
        # Preview
        preview_frame = ttk.LabelFrame(main, text="Preview", padding="10")
        preview_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        self.preview_canvas = tk.Canvas(preview_frame, width=900, height=250, bg='white')
        self.preview_canvas.grid(row=0, column=0)
        
        # Settings
        settings = ttk.LabelFrame(main, text="Settings", padding="10")
        settings.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Scale(settings, from_=0.3, to=5.0, variable=self.scale, orient=tk.HORIZONTAL, command=self.update_scale_label).pack(fill=tk.X)        
        self.scale_label = ttk.Label(settings, text=f"{self.scale.get():.1f}x")
        self.scale_label.pack()
        ttk.Label(settings, textvariable=self.scale).pack()
        
        speed_frame = ttk.Frame(settings)
        speed_frame.pack(fill=tk.X)
        for label, val in [("Instant", "instant"), ("Fastest", "fastest"), ("Fast", "fast"), ("Normal", "normal")]:
            ttk.Radiobutton(speed_frame, text=label, value=val, variable=self.draw_speed).pack(side=tk.LEFT)
        
        ttk.Scale(settings, from_=1, to=10, variable=self.sparsity, orient=tk.HORIZONTAL, command=self.update_sparsity_label).pack(fill=tk.X)
        self.sparsity_label = ttk.Label(settings, text="Medium")
        self.sparsity_label.pack()
        ttk.Label(settings, textvariable=self.sparsity).pack()
        
        offset_frame = ttk.Frame(settings)
        offset_frame.pack(fill=tk.X)
        ttk.Label(offset_frame, text="X:").grid(row=0, column=0)
        ttk.Spinbox(offset_frame, from_=-100, to=100, textvariable=self.offset_x, width=8).grid(row=0, column=1)
        ttk.Label(offset_frame, text="Y:").grid(row=0, column=2)
        ttk.Spinbox(offset_frame, from_=-100, to=100, textvariable=self.offset_y, width=8).grid(row=0, column=3)
        ttk.Button(offset_frame, text="Reset", command=lambda: (self.offset_x.set(0), self.offset_y.set(0))).grid(row=0, column=4)
        
        # Controls
        controls = ttk.LabelFrame(main, text="Controls", padding="10")
        controls.grid(row=2, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        self.draw_btn = ttk.Button(controls, text="Draw (D)", command=self.start_drawing)
        self.draw_btn.pack(fill=tk.X, pady=5)
        
        self.stop_btn = ttk.Button(controls, text="Stop (ESC)", command=self.stop, state='disabled')
        self.stop_btn.pack(fill=tk.X, pady=5)
        
        self.status_label = ttk.Label(controls, text="Ready")
        self.status_label.pack(pady=5)
        
        self.progress = ttk.Progressbar(controls, mode='determinate')
        self.progress.pack(pady=5, fill=tk.X)
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=2)
        main.rowconfigure(1, weight=1)
        
        self.root.bind('<Escape>', lambda e: self.stop())
        self.root.bind('d', lambda e: self.start_drawing())
        self.root.bind('D', lambda e: self.start_drawing())
        
    def set_latex(self, latex):
        self.latex_text.delete('1.0', tk.END)
        self.latex_text.insert('1.0', latex)
        self.generate_preview()
    
    def status(self, msg, color='black'):
        self.status_label.config(text=msg, foreground=color)
        self.root.update_idletasks()

    def update_scale_label(self, value):
        self.scale_label.config(text=f"{float(value):.1f}x")

    def update_sparsity_label(self, value):
        val = int(float(value))
        label = "Dense" if val <= 2 else "Medium" if val <= 4 else "Sparse" if val <= 7 else "Very Sparse"
        self.sparsity_label.config(text=label)    
    
    def render_latex(self, latex, output_file):
        try:
            latex_clean = latex.strip()
            if latex_clean.startswith('$$'):
                latex_clean = latex_clean[2:-2]
            elif latex_clean.startswith('$'):
                latex_clean = latex_clean[1:-1]
            
            url = f"https://latex.codecogs.com/png.image?\\dpi{{600}}\\bg{{white}}{quote(latex_clean)}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                with open(output_file, 'wb') as f:
                    f.write(response.content)
                return True
            return False
        except Exception as e:
            print(f"Render error: {e}")
            return False
    
    def generate_preview(self):
        latex = self.latex_text.get('1.0', tk.END).strip()
        if not latex:
            messagebox.showwarning("Warning", "Enter LaTeX code")
            return
        
        try:
            start_time = time.time()
            self.status("Rendering...", 'orange')
            
            temp_file = 'temp_latex.png'
            
            if not self.render_latex(latex, temp_file):
                messagebox.showerror("Error", "Failed to render LaTeX")
                return
            
            img = Image.open(temp_file)
            img = self.crop_whitespace(img)
            self.preview_pil_image = img.copy()
            
            vec_start = time.time()
            self.drawing_strokes = self.vectorize_image(img)
            vec_time = time.time() - vec_start
            
            canvas_width, canvas_height = 900, 250
            img_width, img_height = img.size
            
            scale_factor = min((canvas_width - 100) / img_width, (canvas_height - 50) / img_height, 1.5)
            new_width = int(img_width * scale_factor)
            new_height = int(img_height * scale_factor)
            
            img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            self.preview_image = ImageTk.PhotoImage(img_resized)
            
            self.preview_canvas.delete('all')
            self.preview_canvas.create_image(50, 20, image=self.preview_image, anchor='nw')
            self.preview_canvas.create_line(20, 5, 45, 15, fill='red', width=3, arrow=tk.LAST)
            self.preview_canvas.create_text(15, 5, text="START", fill='red', anchor='e')
            self.preview_canvas.create_rectangle(50, 20, 50 + new_width, 20 + new_height, outline='gray', dash=(2, 2))
            
            try:
                os.remove(temp_file)
            except:
                pass
            
            total_time = time.time() - start_time
            self.status(f"Ready | {len(self.drawing_strokes)} strokes | {vec_time:.2f}s vec | {total_time:.2f}s total", 'green')
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed:\n{e}")
            self.status("Error", 'red')
    
    def crop_whitespace(self, img):
        gray = img.convert('L')
        inverted = ImageOps.invert(gray)
        bbox = inverted.getbbox()
        
        if bbox:
            left, top, right, bottom = bbox
            width, height = img.size
            border = 5
            
            left = max(0, left - border)
            top = max(0, top - border)
            right = min(width, right + border)
            bottom = min(height, bottom + border)
            
            return img.crop((left, top, right, bottom))
        
        return img
    
    def vectorize_image(self, img):
        gray = img.convert('L')
        pixels = np.array(gray)
        
        binary = (pixels < 200).astype(np.uint8) * 255
        
        contours, hierarchy = cv2.findContours(binary, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_TC89_L1)
        
        if len(contours) == 0:
            return []
        
        all_strokes = []
        sparsity = self.sparsity.get()
        
        for idx, contour in enumerate(contours):
            if len(contour) < 3:
                continue
            
            # Outline
            approx = cv2.approxPolyDP(contour, sparsity * 0.5, closed=True)
            points = [(int(point[0][0]), int(point[0][1])) for point in approx]
            
            if len(points) >= 2:
                outline = []
                for i in range(len(points)):
                    x1, y1 = points[i]
                    x2, y2 = points[(i + 1) % len(points)]
                    
                    dist = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
                    num_points = max(2, int(dist / sparsity))
                    
                    for j in range(num_points):
                        t = j / num_points
                        outline.append((int(x1 + t * (x2 - x1)), int(y1 + t * (y2 - y1))))
                
                if outline:
                    all_strokes.append(outline)
            
            # Fill (outer contours only)
            is_hole = hierarchy is not None and hierarchy[0][idx][3] != -1
            
            if not is_hole:
                x, y, w, h = cv2.boundingRect(contour)
                mask_region = binary[y:y+h, x:x+w].copy()
                fill_spacing = max(1, sparsity)
                
                for row_y in range(0, mask_region.shape[0], fill_spacing):
                    row = mask_region[row_y, :]
                    in_fill = False
                    fill_start = None
                    
                    for col_x in range(len(row)):
                        if row[col_x] > 0 and not in_fill:
                            fill_start = col_x
                            in_fill = True
                        elif row[col_x] == 0 and in_fill:
                            if fill_start is not None and col_x - fill_start > 2:
                                all_strokes.append([(fill_start + x, row_y + y), (col_x + x, row_y + y)])
                            in_fill = False
                            fill_start = None
                    
                    if in_fill and fill_start is not None:
                        all_strokes.append([(fill_start + x, row_y + y), (len(row) + x, row_y + y)])
        
        all_strokes.sort(key=lambda s: min(p[0] for p in s))
        return all_strokes
    
    def start_drawing(self):
        if not self.drawing_strokes:
            messagebox.showwarning("Warning", "Generate preview first")
            return
        
        if self.drawing:
            return
        
        self.drawing = True
        self.draw_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.status("Position mouse at START, then wait...", 'orange')
        
        def delayed_draw():
            time.sleep(3)
            if self.drawing:
                self.draw_strokes()
        
        import threading
        threading.Thread(target=delayed_draw, daemon=True).start()
    
    def stop(self):
        self.drawing = False
        self.status("Stopped", 'red')
        self.draw_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        self.progress['value'] = 0
    
    def draw_strokes(self):
        try:
            start_pos = pyautogui.position()
            start_x = start_pos[0] + self.offset_x.get()
            start_y = start_pos[1] + self.offset_y.get()
            
            start_time = time.time()
            self.status(f"Drawing at ({start_x}, {start_y})...", 'blue')
            
            scale = self.scale.get()
            speed_mode = self.draw_speed.get()
            
            duration_map = {
                "instant": 0,
                "fastest": 0.0001,
                "fast": 0.001,
                "normal": 0.005
            }
            move_duration = duration_map.get(speed_mode, 0)
            
            total_strokes = len(self.drawing_strokes)
            self.progress['maximum'] = total_strokes
            
            for i, stroke in enumerate(self.drawing_strokes):
                if not self.drawing:
                    break
                    
                if len(stroke) < 2:
                    continue
                
                x, y = stroke[0]
                screen_x = start_x + int(x * scale)
                screen_y = start_y + int(y * scale)
                pyautogui.moveTo(screen_x, screen_y, duration=0)
                
                pyautogui.mouseDown()
                
                for point in stroke[1:]:
                    if not self.drawing:
                        break
                    x, y = point
                    screen_x = start_x + int(x * scale)
                    screen_y = start_y + int(y * scale)
                    pyautogui.moveTo(screen_x, screen_y, duration=move_duration)
                
                pyautogui.mouseUp()
                
                if i % 20 == 0 or i == total_strokes - 1:
                    self.progress['value'] = i + 1
                    self.status(f"Drawing... {int((i / total_strokes) * 100)}%", 'blue')
            
            if self.drawing:
                elapsed = time.time() - start_time
                self.status(f"Complete in {elapsed:.2f}s", 'green')
                self.progress['value'] = total_strokes
            else:
                self.progress['value'] = 0
            
            self.drawing = False
            self.draw_btn.config(state='normal')
            self.stop_btn.config(state='disabled')
            
        except Exception as e:
            self.status(f"Error: {str(e)}", 'red')
            messagebox.showerror("Error", f"Drawing failed:\n{str(e)}")
            self.drawing = False
            self.draw_btn.config(state='normal')
            self.stop_btn.config(state='disabled')
            self.progress['value'] = 0

def main():
    root = tk.Tk()
    app = LaTeXDrawer(root)
    root.mainloop()

if __name__ == "__main__":
    main()