# -*- coding: utf-8 -*-
"""3MF (проект Bambu Studio) → GLB без внешних зависимостей: меш из
3D/Objects/*.model, трансформ сборки (масштаб плиты — как напечатано),
Z-up → Y-up, один объект и один материал заданного цвета. Нужен, когда у
фигурки нет .glb, а есть только проект печати — так у бутылки яда.

    py -3 tools/mf2glb.py 3d/poison_prj.3mf out/poison.glb 0.16,0.55,0.25
"""
import sys, zipfile, struct, json
import numpy as np
import xml.etree.ElementTree as ET

NS = '{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}'
P = '{http://schemas.microsoft.com/3dmanufacturing/production/2015/06}'
IDENTITY = '1 0 0 0 1 0 0 0 1 0 0 0'


def mat(t):
    """3MF transform: 12 чисел — 3×3 по строкам, затем смещение."""
    v = [float(x) for x in t.split()]
    m = np.eye(4); m[:3, :3] = np.array(v[:9]).reshape(3, 3).T; m[:3, 3] = v[9:]
    return m


def convert(src, dst, color=(0.7, 0.7, 0.7)):
    z = zipfile.ZipFile(src)
    root = ET.fromstring(z.read('3D/3dmodel.model'))
    M = mat(root.find(f'{NS}build/{NS}item').get('transform', IDENTITY))
    comp = root.find(f'.//{NS}component')
    if comp is not None:                       # меш вынесен в отдельный файл
        path = comp.get(f'{P}path').lstrip('/')
        M = M @ mat(comp.get('transform', IDENTITY))
    else:
        path = '3D/3dmodel.model'
    vs, tris = [], []
    for _, el in ET.iterparse(z.open(path), events=('end',)):      # потоково: файл на десятки МБ
        if el.tag == f'{NS}vertex':
            vs.append((float(el.get('x')), float(el.get('y')), float(el.get('z')))); el.clear()
        elif el.tag == f'{NS}triangle':
            tris.append((int(el.get('v1')), int(el.get('v2')), int(el.get('v3')))); el.clear()
    V = (M[:3, :3] @ np.array(vs, np.float64).T).T + M[:3, 3]
    V -= V.mean(0)
    V = (V[:, [0, 2, 1]] * np.array([1, 1, -1])).astype(np.float32)   # Z-up → Y-up
    T = np.array(tris, np.uint32)

    vb, ib = V.tobytes(), T.tobytes()
    bin_ = vb + ib + b'\0' * ((4 - len(vb + ib) % 4) % 4)
    gltf = {
        'asset': {'version': '2.0', 'generator': 'mf2glb'},
        'scene': 0, 'scenes': [{'nodes': [0]}], 'nodes': [{'mesh': 0}],
        'meshes': [{'primitives': [{'attributes': {'POSITION': 0}, 'indices': 1, 'material': 0}]}],
        'materials': [{'pbrMetallicRoughness': {'baseColorFactor': [*color, 1.0], 'metallicFactor': 0.0, 'roughnessFactor': 0.6}}],
        'accessors': [
            {'bufferView': 0, 'componentType': 5126, 'count': len(V), 'type': 'VEC3',
             'min': V.min(0).tolist(), 'max': V.max(0).tolist()},
            {'bufferView': 1, 'componentType': 5125, 'count': int(T.size), 'type': 'SCALAR'}],
        'bufferViews': [{'buffer': 0, 'byteOffset': 0, 'byteLength': len(vb), 'target': 34962},
                        {'buffer': 0, 'byteOffset': len(vb), 'byteLength': len(ib), 'target': 34963}],
        'buffers': [{'byteLength': len(bin_)}],
    }
    js = json.dumps(gltf, separators=(',', ':')).encode()
    js += b' ' * ((4 - len(js) % 4) % 4)
    with open(dst, 'wb') as f:
        f.write(struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(bin_)))
        f.write(struct.pack('<II', len(js), 0x4E4F534A)); f.write(js)
        f.write(struct.pack('<II', len(bin_), 0x004E4942)); f.write(bin_)
    return len(V), len(T), [round(float(v), 1) for v in V.max(0) - V.min(0)]


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    color = tuple(float(v) for v in sys.argv[3].split(',')) if len(sys.argv) > 3 else (0.7, 0.7, 0.7)
    nv, nt, size = convert(sys.argv[1], sys.argv[2], color)
    print(f'{nv} вершин, {nt} треугольников, габарит {size} мм')
    print(sys.argv[2])
