# ATRCenterTask

Centra los iconos de aplicaciones abiertas en la barra de tareas de Windows 10, igual que hace Windows 11 por defecto.

Corre en segundo plano como un icono en la bandeja del sistema y se ajusta automáticamente cada vez que abres, cierras o minimizas una ventana.

---

## Uso rapido (exe)

Descarga o compila `ATRCenterTask.exe` y ejecutalo. No requiere instalacion.

- Se agrega automaticamente al inicio de Windows.
- Para pausarlo o cerrarlo: click derecho en el icono de la bandeja del sistema.

---

## Compilar desde codigo fuente

**Requisitos:** Python 3.10+

```bat
build.bat
```

El ejecutable queda en `dist\ATRCenterTask.exe`.

### Pasos manuales (opcional)

```bat
pip install -r requirements.txt
pip install pyinstaller
python -m PyInstaller ATRCenterTask.spec
```

---

## Ejecutar sin compilar

```bat
pip install -r requirements.txt
python ATRCenterTask.py
```

---

## Diagnostico

`inspect_taskbar.py` imprime informacion sobre los botones de la barra de tareas detectados por UIAutomation. Util para depurar si el centrado no funciona correctamente.

```bat
python inspect_taskbar.py
```
