using System;
using UnityEngine;

namespace SphericalCivilization
{
    [Serializable]
    public sealed class ReferenceWorld
    {
        public int schemaVersion;
        public ReferenceTile[] tiles;
    }

    [Serializable]
    public sealed class ReferenceTile
    {
        public int id;
        public Vector3 center;
        public Vector3 normal;
        public Vector3[] vertices;
        public ReferenceColor color;
        public string terrain;
        public int[] neighbors;
    }

    [Serializable]
    public struct ReferenceColor
    {
        public float r, g, b;
        public Color Linear => new Color(r, g, b, 1f).linear;
    }
}
