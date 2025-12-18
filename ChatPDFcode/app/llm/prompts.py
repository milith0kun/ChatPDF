"""
Prompt Templates
Structured prompts for the RAG system
"""

# System prompt for the academic document assistant
SYSTEM_PROMPT = """Eres un asistente experto en análisis de documentos académicos. Tu rol es responder preguntas basándote EXCLUSIVAMENTE en el contenido de los documentos proporcionados.

REGLAS ESTRICTAS:
1. SOLO responde usando información que esté explícitamente presente en los fragmentos de contexto proporcionados.
2. NUNCA inventes, especules ni agregues información que no esté en los documentos.
3. Cuando cites información, indica el documento y página de origen usando el formato: [Doc: nombre, Pág: X]
4. Si la información solicitada NO está en los documentos, responde claramente: "Esta información no se encuentra en los documentos proporcionados."
5. Si la información es parcial o incompleta, indícalo explícitamente.
6. Mantén un tono profesional y académico.
7. Cuando sea apropiado, organiza la respuesta con viñetas o numeración para mayor claridad.

FORMATO DE RESPUESTA:
- Comienza directamente con la respuesta, sin preámbulos innecesarios.
- Incluye citas de las fuentes entre corchetes.
- Si hay múltiples perspectivas en los documentos, preséntalas todas.
- Concluye con cualquier limitación relevante sobre la información disponible."""


# Template for building context prompt
CONTEXT_TEMPLATE = """A continuación se presentan fragmentos relevantes de los documentos cargados por el usuario. Usa ÚNICAMENTE esta información para responder.

=== CONTEXTO DE DOCUMENTOS ===
{context}
=== FIN DEL CONTEXTO ===

Pregunta del usuario: {query}

Instrucciones adicionales:
- Basa tu respuesta SOLO en el contexto anterior.
- Cita las fuentes específicas usando [Doc: nombre, Pág: X].
- Si la respuesta no está en el contexto, indícalo claramente."""


# Template for vision analysis
VISION_ANALYSIS_PROMPT = """Analiza esta imagen que proviene de un documento académico.

Por favor proporciona:
1. TIPO: Identifica qué tipo de elemento visual es (gráfico de barras, diagrama de flujo, tabla, fotografía, ecuación, etc.)
2. CONTENIDO: Describe detalladamente lo que muestra la imagen.
3. DATOS: Si hay datos cuantitativos visibles (números, porcentajes, valores), extráelos.
4. TENDENCIAS: Si es un gráfico, describe las tendencias principales.
5. CONTEXTO: Cómo se relaciona esta imagen con el texto circundante (si se proporciona).

Contexto textual circundante: {context}

Responde en español y sé lo más específico posible con los datos visibles."""


# Template for anti-hallucination validation
VALIDATION_PROMPT = """Revisa la siguiente respuesta y verifica que CADA afirmación esté respaldada por el contexto proporcionado.

RESPUESTA A VALIDAR:
{response}

CONTEXTO ORIGINAL:
{context}

Por cada afirmación en la respuesta, indica:
1. Si está respaldada por el contexto (SÍ/NO)
2. La cita específica del contexto que la respalda

Si encuentras afirmaciones no respaldadas, indica cuáles son."""


def build_context_prompt(context: str, query: str) -> str:
    """Build the context prompt with provided context and query."""
    return CONTEXT_TEMPLATE.format(context=context, query=query)


def build_vision_prompt(context: str = "") -> str:
    """Build the vision analysis prompt."""
    return VISION_ANALYSIS_PROMPT.format(context=context or "No disponible")


def build_validation_prompt(response: str, context: str) -> str:
    """Build the validation prompt for anti-hallucination check."""
    return VALIDATION_PROMPT.format(response=response, context=context)
