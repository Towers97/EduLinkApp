key = "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" 
import tkinter as tk
from tkinter import scrolledtext, messagebox, font
import threading
import requests
import os
from datetime import datetime
from docx import Document 
import json
import re # Necesario para las Expresiones Regulares de Markdown

# ==============================================================================
# ⚠️ CONFIGURACIÓN CLAVE: PEGA TU CLAVE DE OPENROUTER AQUÍ
# ==============================================================================
# Si esta clave no es válida, la aplicación devolverá un error 401/403 de la API.
API_KEY = key
# ==============================================================================

# === RUTAS Y URLS ===
CONFIG_PATH = "parametros.docx"
KNOWLEDGE_PATH = "base_conocimiento.txt" 
BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "conversacion_subteacher.txt")

# === CARGA DE CONOCIMIENTO EXTERNO ===
def load_external_knowledge(file_path):
    """Carga el contenido de la base de conocimiento local."""
    if not os.path.exists(file_path):
        print(f"Base de conocimiento '{file_path}' no encontrada. Usando base vacía.")
        return ""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception as e:
        print(f"Error al leer la base de conocimiento: {e}")
        return ""

# === LÓGICA DE CARGA DE PERSONALIDAD ===
def load_personality(doc_path):
    """Carga la configuración de personalidad desde un archivo DOCX."""
    # ... (La lógica de load_personality es la misma que la anterior) ...
    config = {
        "ROL": "Subteacher",
        "MODELO": "deepseek/deepseek-r1:free", 
        "TEMPERATURA": 0.7,
        "SISTEMA": "Eres Subteacher, un asistente educativo. Tu objetivo es guiar al estudiante con pistas (hints) paso a paso sin darle la solución directa.",
        "DESCRIPCIÓN": "",
        "OBJETIVO": "",
        "TONO": "",
        "MODO": "",
    }

    if not os.path.exists(doc_path):
        messagebox.showwarning("Aviso", f"No se encontró el archivo '{doc_path}'. Se usarán valores por defecto.")
        return config

    try:
        doc = Document(doc_path)
        for p in doc.paragraphs:
            text = p.text.strip()
            if ":" in text:
                key, value = text.split(":", 1)
                key = key.strip().upper()
                value = value.strip()
                
                if key == "TEMPERATURA":
                    try:
                        config[key] = float(value)
                    except ValueError:
                        print(f"Advertencia: Valor de TEMPERATURA '{value}' no válido. Usando 0.7.")
                elif key in config: 
                    config[key] = value
        
        if config["DESCRIPCIÓN"]:
            system_prompt = config["DESCRIPCIÓN"].strip()
            if config["OBJETIVO"]:
                system_prompt += f" Tu OBJETIVO principal es: {config['OBJETIVO'].strip()}."
            if config["TONO"]:
                system_prompt += f" Tu TONO debe ser: {config['TONO'].strip()}."
            if config["MODO"]:
                system_prompt += f" Tu MODO de operación es: {config['MODO'].strip()}."
            config["SISTEMA"] = system_prompt
        elif config["OBJETIVO"] or config["MODO"]:
             current_system = config.get("SISTEMA", "Eres un asistente amigable.")
             if config["OBJETIVO"]:
                  current_system += f" Tu objetivo específico es: {config['OBJETIVO']}."
             if config["MODO"]:
                  current_system += f" Trabajas en modo: {config['MODO']}."
             config["SISTEMA"] = current_system

    except Exception as e:
        messagebox.showerror("Error de lectura", f"No se pudo leer el archivo DOCX: {e}")
        return config
    
    return config

# === CONFIGURACIÓN GLOBAL ===
PERSONA = load_personality(CONFIG_PATH) 
EXTERNAL_KNOWLEDGE = load_external_knowledge(KNOWLEDGE_PATH)

# === FUNCIONES DE LOGGING ===
def init_log():
    """Inicializa la carpeta de logs y añade encabezado al archivo."""
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write("\n" + "="*60 + "\n")
        f.write(f"📅 Nueva sesión ({PERSONA['ROL']}) iniciada: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Configuración: Modelo={PERSONA['MODELO']}, Temp={PERSONA.get('TEMPERATURA', 0.7)}\n")
        if EXTERNAL_KNOWLEDGE:
             # Dejamos esta línea en el log, ya que es información de depuración
             f.write("⚠️ Se está utilizando una Base de Conocimiento Externa.\n") 
        f.write("="*60 + "\n\n")

def append_to_log(role, message):
    """Añade un mensaje al archivo de log."""
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        timestamp = datetime.now().strftime("[%H:%M]")
        if role == "user":
            f.write(f"{timestamp} Alumno: {message}\n\n")
        elif role == "assistant":
            f.write(f"{timestamp} {PERSONA['ROL']}: {message}\n\n")


# === FUNCIÓN PARA LLAMAR AL MODELO ===
def ask_deepseek(messages_to_send):
    """Realiza la llamada a la API usando el historial de mensajes dado."""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": PERSONA["MODELO"],
        "messages": messages_to_send, 
        "temperature": PERSONA.get("TEMPERATURA", 0.7),
        "max_tokens": 700
    }

    try:
        r = requests.post(BASE_URL, headers=headers, json=data, timeout=60)
        
        if r.status_code == 200:
            res = r.json()
            if res.get("choices") and res["choices"][0].get("message"):
                 return res["choices"][0]["message"]["content"]
            else:
                 return f"⚠️ Respuesta incompleta del modelo: {json.dumps(res, indent=2)}"
        elif r.status_code == 401:
            return "❌ Error 401: Clave API no válida o expirada. Revisa tu API_KEY."
        else:
            return f"⚠️ Error HTTP {r.status_code}: {r.text}"
            
    except requests.exceptions.RequestException as e:
        return f"❌ Error de conexión/Timeout: {e}"


class DeepSeekChatApp:
    def __init__(self, master):
        self.master = master
        self.master.title(f"{PERSONA['ROL']} Cobot 🎓")
        self.master.geometry("800x600")
        self.master.configure(bg="#1c1c1c")
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)
        
        self.chat_history = [{"role": "system", "content": PERSONA["SISTEMA"]}]
        self.placeholder = "💬 Escribe aquí tu mensaje..."
        self.rol = PERSONA['ROL']
        
        # Almacena el índice de inicio del mensaje "pensando..." para eliminarlo
        self.thinking_start_index = None 
        
        # Bandera para controlar el estado del placeholder 
        self.placeholder_active = False 
        
        self.setup_ui()
        self.init_tags()
        self.display_welcome_message()

    def init_tags(self):
        """Inicializa las etiquetas de Tkinter, incluyendo las de formato Markdown y Math."""
        # Estilos base
        self.chat_box.tag_configure("user", foreground="#a970ff", font=("Segoe UI", 11, "bold"))
        self.chat_box.tag_configure("assistant_prefix", foreground="white", font=("Segoe UI", 11, "bold"))
        self.chat_box.tag_configure("thinking_tag", foreground="#777777", font=("Segoe UI", 11, "italic"))
        self.chat_box.tag_configure("normal_text", foreground="white", font=("Segoe UI", 11))

        # Estilos Markdown para texto
        self.chat_box.tag_configure("bold", font=("Segoe UI", 11, "bold"), foreground="white")
        self.chat_box.tag_configure("italic", font=("Segoe UI", 11, "italic"), foreground="white")
        self.chat_box.tag_configure("bold_italic", font=("Segoe UI", 11, "bold italic"), foreground="white")
        
        # Estilos para Math (fracciones, ecuaciones)
        math_font = font.Font(family="Courier New", size=11) # Fuente monoespaciada
        # Math Inline: se destaca con fondo oscuro y color de texto cian
        self.chat_box.tag_configure("math_inline", background="#2a2a2a", foreground="#00e0e0", font=math_font)
        # Math Block: se destaca con fondo un poco más oscuro y color de texto verde azulado
        self.chat_box.tag_configure("math_block", background="#202020", foreground="#00ffcc", font=math_font)
        
        # Estilo Markdown para Listas (Sangría para el cuerpo de la lista)
        self.chat_box.tag_configure("list_item", lmargin1=20, lmargin2=20, font=("Segoe UI", 11), foreground="white")


    def setup_ui(self):
        """Configura todos los widgets de la interfaz."""
        
        title_text = "Edulink"
        title = tk.Label(self.master, text=title_text, bg="#1c1c1c", fg="#a970ff", font=("Segoe UI", 18, "bold"))
        title.pack(pady=10)

        # Chat box
        self.chat_box = scrolledtext.ScrolledText(self.master, wrap=tk.WORD, width=90, height=22, 
                                                bg="#121212", fg="white", font=("Segoe UI", 11), 
                                                bd=0, relief=tk.FLAT, padx=10, pady=10)
        self.chat_box.pack(padx=10, pady=(0, 10), fill=tk.BOTH, expand=True)
        self.chat_box.configure(state="disabled")

        # Entrada y botón
        entry_frame = tk.Frame(self.master, bg="#1c1c1c")
        entry_frame.pack(padx=10, pady=(0,10), fill=tk.X)

        self.entry = tk.Text(entry_frame, height=6, width=90, bg="#2a2a2a", fg="white", 
                            font=("Segoe UI", 11), wrap=tk.WORD, insertbackground="#a970ff", 
                            bd=0, relief=tk.FLAT, padx=5, pady=5)
        self.entry.pack(side=tk.LEFT, padx=(0,10), fill=tk.X, expand=True)
        
        self.send_btn = tk.Button(entry_frame, text="Enviar", command=self.send_message, 
                                bg="#a970ff", fg="#1c1c1c", font=("Segoe UI", 11, "bold"), 
                                width=10, height=3, activebackground="#8c58cc", activeforeground="#1c1c1c")
        self.send_btn.pack(side=tk.RIGHT)

        # Eventos y Placeholder
        self.entry.bind("<FocusIn>", self.remove_placeholder)
        self.entry.bind("<FocusOut>", self.add_placeholder)
        self.entry.bind("<Return>", self.on_enter_key)
        self.add_placeholder()

    # === LÓGICA CORREGIDA DEL PLACEHOLDER ===

    def add_placeholder(self, event=None):
        """Maneja la inserción del texto placeholder cuando se pierde el foco."""
        # Nota: current_text.strip() maneja el salto de línea residual de tk.Text
        current_text = self.entry.get("1.0", tk.END).strip()
        
        # Solo inserta si la caja está vacía Y el placeholder NO está activo
        if not current_text and not self.placeholder_active:
            self.entry.insert("1.0", self.placeholder)
            self.entry.config(fg="#777777")
            self.placeholder_active = True

    def remove_placeholder(self, event=None):
        """Maneja la eliminación del texto placeholder cuando se gana el foco."""
        # Solo elimina si el placeholder está activo
        if self.placeholder_active:
            self.entry.delete("1.0", tk.END)
            self.entry.config(fg="white") # Prepara el color para texto real
            self.placeholder_active = False

    # === FIN LÓGICA CORREGIDA DEL PLACEHOLDER ===


    def on_enter_key(self, event):
        """Permite enviar el mensaje con la tecla Enter."""
        # Solo envía si el botón no está deshabilitado
        if self.send_btn['state'] == tk.NORMAL and not event.state & 0x4: # Verifica si Ctrl NO está presionado
            self.send_message()
            return "break" # Evita que Tkinter inserte una nueva línea

    # === Lógica de Formato Markdown (Actualizada con Listas y Math) ===
    def apply_markdown_format(self, text):
        """
        Procesa el texto Markdown del modelo línea por línea.
        Soporta: Listas (- item, 1. item), y dentro de las líneas: Math ($$, $), **negrita**, *cursiva*.
        """
        lines = text.split('\n')
        
        for line in lines:
            stripped_line = line.strip()
            
            # === 1. PROCESAR LISTAS (Bullet Points y Listas Numeradas) ===
            is_list_item = False
            list_prefix = ''
            content_to_format = stripped_line
            
            if stripped_line.startswith(('- ', '* ')):
                list_prefix = '• ' # Símbolo de bullet point
                content_to_format = stripped_line[2:].strip()
                is_list_item = True
            elif re.match(r'^\d+\.\s', stripped_line):
                # Captura el prefijo numérico (e.g., "1. ")
                match = re.match(r'(\d+\.\s)(.*)', stripped_line)
                if match:
                    list_prefix = match.group(1)
                    content_to_format = match.group(2).strip()
                    is_list_item = True
            
            if is_list_item:
                # Insertar el prefijo de la lista (bullet o número)
                self.chat_box.insert(tk.END, list_prefix, "normal_text")
                
                # Aplicar formato de lista y luego el formato de texto/negrita/math al contenido
                self.apply_segment_formatting(content_to_format, "list_item")
                self.chat_box.insert(tk.END, "\n") # Salto de línea después del ítem
                continue

            # === 2. PROCESAR TEXTO NORMAL (sin prefijo de lista) ===
            if line: # Si no es una línea vacía
                self.apply_segment_formatting(line, "normal_text")
            
            self.chat_box.insert(tk.END, "\n")


    def apply_segment_formatting(self, segment, default_tag):
        """
        Aplica formatos Math ($$, $) y de texto (**negrita**, *cursiva*) 
        dentro de un segmento de texto.
        
        Patrón de Match Groups:
        1: $$...$$ completo (Math Block)
        2: $...$ completo (Math Inline)
        3: Delimitador de texto (***, **, *)
        4: Contenido de texto (para los grupos 3)
        5: Segundo delimitador de texto (para asegurar simetría en regex)
        """
        
        # Combinación de regex para capturar: Math Block, Math Inline, Text Formats
        # El grupo 5 asegura que la regex de texto use el mismo delimitador para cerrar
        pattern = r'(\$\$.+?\$\$)|(\$.+?\$)|(\*\*\*|\*\*|\*)(.+?)(\3)'
        
        current_text_index = 0
        
        for match in re.finditer(pattern, segment, re.DOTALL):
            match_start = match.start()
            match_end = match.end()

            # 1. Insertar el texto normal antes del match
            if match_start > current_text_index:
                normal_text = segment[current_text_index:match_start]
                self.chat_box.insert(tk.END, normal_text, default_tag)
            
            # Inicializar variables para el contenido del match
            tag_to_apply = default_tag
            content_to_insert = ""

            # 2. Determinar el tipo de formato y el contenido
            if match.group(1): # Math Block: $$...$$
                tag_to_apply = "math_block"
                content_to_insert = match.group(1)[2:-2].strip() # Elimina $$
            
            elif match.group(2): # Math Inline: $...$
                tag_to_apply = "math_inline"
                content_to_insert = match.group(2)[1:-1].strip() # Elimina $
            
            elif match.group(3): # Text Formats: ***, **, *
                delimiter = match.group(3)
                content = match.group(4)
                
                if delimiter == '***':
                    tag_to_apply = "bold_italic"
                elif delimiter == '**':
                    tag_to_apply = "bold"
                elif delimiter == '*':
                    tag_to_apply = "italic"
                
                content_to_insert = content
            
            # 3. Insertar el contenido formateado
            self.chat_box.insert(tk.END, content_to_insert, tag_to_apply)
            
            # 4. Actualizar el índice de inicio para la próxima iteración
            current_text_index = match_end

        # 5. Insertar cualquier texto restante después del último match
        remaining_text = segment[current_text_index:]
        if remaining_text:
             self.chat_box.insert(tk.END, remaining_text, default_tag)


    def send_message(self):
        """Captura el mensaje de la UI y lo procesa en un hilo separado."""
        user_msg = self.entry.get("1.0", tk.END).strip()
        if not user_msg or user_msg == self.placeholder: 
            return

        # 1. Mostrar mensaje del usuario en la caja de chat
        self.chat_box.configure(state="normal")
        self.chat_box.insert(tk.END, f"🧑 Alumno: {user_msg}\n", "user")
        self.chat_box.configure(state="disabled")
        
        # 2. Limpiar entrada. 
        self.entry.delete("1.0", tk.END) 
        # Si había texto real, la bandera es False, se puede volver a poner el placeholder.
        self.placeholder_active = False
        self.add_placeholder() 
        
        # 3. Guardar mensaje de usuario en el log
        append_to_log("user", user_msg)

        # 4. Iniciar procesamiento en segundo plano (hilo)
        threading.Thread(target=self.process_message, args=(user_msg,), daemon=True).start()


    def process_message(self, user_msg):
        """Llama a la API, recibe la respuesta y actualiza la UI y el historial."""
        
        # INICIO: Deshabilitar entrada y botón de envío
        self.send_btn.config(state=tk.DISABLED, text="Pensando...") 
        self.entry.config(state=tk.DISABLED)

        # 1. MOSTRAR MENSAJE TEMPORAL DE PROCESAMIENTO
        THINKING_MESSAGE = "🤖 Edulink está pensando..."
        self.chat_box.configure(state="normal")
        
        # CORRECCIÓN DE ÍNDICE: Almacenar el índice final antes de insertar el mensaje temporal.
        # Esto asegura que la eliminación posterior funcione correctamente.
        self.thinking_start_index = self.chat_box.index(tk.END) 
        
        self.chat_box.insert(tk.END, f"\n{THINKING_MESSAGE}\n", "thinking_tag") 
        self.chat_box.see(tk.END)
        self.chat_box.configure(state="disabled")
        
        # 2. CONSTRUIR EL MENSAJE A ENVIAR (con la inyección de conocimiento RAG)
        messages_to_send = self.chat_history.copy()
        
        if EXTERNAL_KNOWLEDGE:
            context_message = {
                "role": "user", 
                "content": (
                    "## CONTEXTO DE CONOCIMIENTO EXTERNO\n"
                    f"--- CONOCIMIENTO ---\n{EXTERNAL_KNOWLEDGE}\n\n"
                    f"--- PREGUNTA DEL USUARIO ---\n{user_msg}"
                )
            }
            messages_to_send.append(context_message)
        else:
            messages_to_send.append({"role": "user", "content": user_msg})

        # 3. Llamar a la API
        reply = ask_deepseek(messages_to_send)
        
        # 4. ELIMINAR MENSAJE TEMPORAL
        self.chat_box.configure(state="normal")
        if self.thinking_start_index:
             # Eliminar desde el índice de inicio hasta el final de la caja de chat
             self.chat_box.delete(self.thinking_start_index, tk.END)
             self.thinking_start_index = None # Resetear el índice
        
        # 5. ACTUALIZAR HISTORIAL GLOBAL
        self.chat_history.append({"role": "user", "content": user_msg})
        self.chat_history.append({"role": "assistant", "content": reply})

        # 6. Mostrar respuesta en la UI (APLICANDO FORMATO)
        self.chat_box.insert(tk.END, "\n") # ⬅️ AÑADIDO: Garantiza un salto de línea limpio.
        self.chat_box.insert(tk.END, f"🤖 {self.rol}: ", "assistant_prefix")
        self.apply_markdown_format(reply.strip())
        self.chat_box.insert(tk.END, "\n\n") # Doble salto de línea al final
        self.chat_box.see(tk.END)
        self.chat_box.configure(state="disabled")

        # 7. Guardar respuesta en el log
        append_to_log("assistant", reply)
        
        # FIN: Volver a habilitar la entrada y el botón
        self.entry.config(state=tk.NORMAL)
        self.send_btn.config(state=tk.NORMAL, text="Enviar")

    def display_welcome_message(self):
        """Muestra el mensaje de bienvenida inicial."""
        self.chat_box.configure(state="normal")
        self.chat_box.insert(tk.END, f"🤖 {self.rol}: ¡Hola! 👋 Soy tu co-docente. Escribe tu duda y te daré pistas paso a paso.\n\n", "assistant_prefix")
        # La referencia al archivo KNOWLEDGE_PATH fue eliminada previamente.
        self.chat_box.configure(state="disabled")

    def on_close(self):
        """Maneja el cierre de la ventana."""
        self.master.destroy()


# === INICIO DE LA APLICACIÓN ===
if __name__ == "__main__":
    init_log() 
    root = tk.Tk()
    app = DeepSeekChatApp(root)
    root.mainloop()