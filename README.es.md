# Frugal

**Gasta menos tokens en Claude Code sin perder calidad.** Una skill pequeña y una herramienta
en Python que funciona en Windows, Mac y Linux: muestra qué llena tu contexto, recorta lo que
se carga en cada sesión y guarda tu avance antes de limpiar una sesión larga.

Estado: **0.1 beta.** Probada con pruebas automáticas en Linux (Python 3.11 a 3.13). Las
comprobaciones para Windows y macOS están en [MANUAL_CHECKS.md](MANUAL_CHECKS.md).

## Por qué

Cada mensaje que envías vuelve a enviar toda la conversación. Todo lo que Claude leyó queda en
ese historial y se paga de nuevo en cada turno; además, un contexto largo y lleno de ruido
empeora las respuestas. Frugal ataca lo que sí puedes controlar:

1. **Lo que se carga en cada sesión** (`doctor`): CLAUDE.md demasiado grande, reglas sin filtro
   de ruta, demasiadas skills o servidores MCP, instrucciones viejas.
2. **Lo que realmente gastó contexto** (`audit`): tus propios registros de sesión, ordenados por
   herramienta y por resultado, y el contexto máximo que alcanzó un mensaje.
3. **Lo que pierdes al limpiar** (`handover`): un HANDOVER.md corto para que la sesión nueva
   empiece liviana y sepa el objetivo, las decisiones y el siguiente paso.

También aplica hábitos de trabajo baratos (buscar antes de leer, leer trozos, modificar en vez
de reescribir, limitar la salida de comandos) y puede bloquear la lectura de carpetas de
compilación y dependencias.

**No** desactiva el razonamiento, no acorta respuestas ni cambia de modelo. Eso puede bajar la calidad.

## Instalación

Requiere Python 3.8+ y Claude Code. Sin otras dependencias.

Copia la carpeta `skills/frugal` a:

| Alcance | Carpeta |
|---|---|
| Solo este proyecto | `<proyecto>/.claude/skills/frugal` |
| Todos tus proyectos (macOS/Linux) | `~/.claude/skills/frugal` |
| Todos tus proyectos (Windows) | `%USERPROFILE%\.claude\skills\frugal` |

Claude carga la skill cuando hablas de tokens, contexto, costo, `/clear` o `/compact`.

## Uso

Ejecútalos tú o pídele a Claude que lo haga, desde la carpeta de la skill (usa `python3` o `py`
si `python` no se encuentra):

```
python scripts/frugal.py --lang es doctor                 # qué se carga en cada sesión
python scripts/frugal.py --lang es audit --project .      # qué gastó contexto en este proyecto
python scripts/frugal.py --lang es handover --write       # crear/agregar HANDOVER.md
python scripts/frugal.py --lang es init-config            # simulación: reglas propuestas
python scripts/frugal.py --lang es init-config --apply    # escribirlas (con copia de seguridad)
python scripts/frugal.py --lang es init-config --global --hooks --apply   # aviso automático a ~150k de contexto
```

### Seguridad

- Todo es de solo lectura, salvo `handover --write` y `init-config --apply`.
- `init-config` nunca quita reglas ni otras opciones, se niega a tocar un archivo que no puede
  leer y hace una copia de seguridad con fecha antes de cambiar algo.
- `handover --write` agrega en vez de sobrescribir y añade `HANDOVER.md` a `.gitignore`
  (solo en repositorios git; `--no-gitignore` para omitirlo), porque puede contener detalles
  del proyecto.
- `audit` lee los registros que Claude Code guarda en tu propio equipo y no envía nada.
  Su salida puede incluir comandos y nombres de archivos: revísala antes de compartirla.

### Mide, no adivines

El ahorro depende de cómo trabajes. Para ver el tuyo:

```
python scripts/frugal.py audit --json > antes.json
# trabaja un tiempo con los hábitos y ajustes de Frugal
python scripts/frugal.py audit --json > despues.json
```

Compara `new_token_spend` y `peak_context` en tareas parecidas.

## Licencia

MIT. Basado en [save_tokens_skill](https://github.com/roeea2/save_tokens_skill) de RoeeAI (MIT);
ver [NOTICE](NOTICE). Hecho por YSA Apps.
