// Topology, geometry and picking checks only; no UI input or menu interaction.
var globe = UnityEngine.Object.FindFirstObjectByType<SphericalCivilization.GlobePreview>();
var source = UnityEngine.JsonUtility.FromJson<SphericalCivilization.ReferenceWorld>(globe.worldAsset.text);
var world = globe.Topology;
void Require(bool condition, string message) { if (!condition) throw new System.Exception(message); }
double Area(int[] vertices, SphericalCivilization.World.OperationalWorld map, UnityEngine.Vector3 u, UnityEngine.Vector3 v)
{
    double sum = 0;
    for(int i=0;i<vertices.Length;i++)
    {
        var a=map.Vertices[vertices[i]];var b=map.Vertices[vertices[(i+1)%vertices.Length]];
        sum+=(double)UnityEngine.Vector3.Dot(a,u)*UnityEngine.Vector3.Dot(b,v)-(double)UnityEngine.Vector3.Dot(a,v)*UnityEngine.Vector3.Dot(b,u);
    }
    return sum*0.5;
}
object Validate(SphericalCivilization.World.OperationalWorld map,int expectedCount,int pentagonCount=0)
{
    Require(map.Tiles.Count==642 && map.Boundaries.Count==1920,"Parent topology changed.");
    Require(map.Vertices.Count-map.Edges.Count+map.Subtiles.Count==2,"Operational mesh is not a closed spherical manifold.");
    int pentagons=0,crossRegion=0;
    double worstAreaError=0,worstSurfaceAreaRatio=0;
    foreach(var tile in map.Tiles)
    {
        if(tile.Corners.Length==5)pentagons++;
        var u=UnityEngine.Vector3.Cross(tile.Normal,UnityEngine.Vector3.right);
        if(u.sqrMagnitude<0.1f)u=UnityEngine.Vector3.Cross(tile.Normal,UnityEngine.Vector3.up);
        u.Normalize();var v=UnityEngine.Vector3.Cross(tile.Normal,u).normalized;
        double parentArea=Area(tile.Corners,map,u,v),area=0,minimum=double.MaxValue,maximum=0;
        Require(tile.SubtileIndices.Length==(tile.Corners.Length==5 && pentagonCount>0?pentagonCount:expectedCount),"Requested subtile count was not respected in parent "+tile.Id);
        foreach(int index in tile.SubtileIndices)
        {
            var cell=map.Subtiles[index];
            Require(cell.ParentTileId==tile.Id && (int)(cell.Id>>32)==tile.Id,"A cell lost its parent or stable ID.");
            double cellArea=Area(cell.Vertices,map,u,v);
            Require(cellArea>1e-12,"Collapsed or inverted operational cell.");
            double surfaceArea=0;
            for(int side=0;side<cell.Vertices.Length;side++)
            {
                var a=map.Vertices[cell.Vertices[side]];var b=map.Vertices[cell.Vertices[(side+1)%cell.Vertices.Length]];
                surfaceArea+=UnityEngine.Vector3.Cross(a-cell.Center,b-cell.Center).magnitude*0.5;
                var next=map.Vertices[cell.Vertices[(side+2)%cell.Vertices.Length]];
                Require(UnityEngine.Vector3.Dot(UnityEngine.Vector3.Cross(b-a,next-b),tile.Normal)>=-parentArea*0.000002,
                    "Non-convex subtile: "+cell.Id);
            }
            Require(surfaceArea>0 && !double.IsNaN(surfaceArea),"Invalid 3D surface area.");
            minimum=System.Math.Min(minimum,surfaceArea);maximum=System.Math.Max(maximum,surfaceArea);
            area+=cellArea;
        }
        double relative=System.Math.Abs(area-parentArea)/parentArea;
        worstAreaError=System.Math.Max(worstAreaError,relative);
        Require(relative<0.0001,"Subtiles do not cover their parent: "+tile.Id+"; relative area error="+relative);
        double ratio=maximum/minimum;worstSurfaceAreaRatio=System.Math.Max(worstSurfaceAreaRatio,ratio);
    }
    Require(pentagons==12,"Pentagon regions were lost.");
    for(int index=0;index<map.Subtiles.Count;index++)
    {
        var cell=map.Subtiles[index];
        Require(map.SubtileIndicesById[cell.Id]==index,"Duplicate or unstable subtile ID.");
        for(int side=0;side<cell.Vertices.Length;side++)
        {
            var edge=map.Edges[cell.Edges[side]];int neighbor=cell.Neighbors[side];
            Require(neighbor!=index && (edge.FirstSubtile==index && edge.SecondSubtile==neighbor ||
                edge.SecondSubtile==index && edge.FirstSubtile==neighbor),"Incorrect edge ownership.");
            var other=map.Subtiles[neighbor];int otherSide=System.Array.IndexOf(other.Edges,edge.Id);
            Require(otherSide>=0 && other.Neighbors[otherSide]==index,"Non-reciprocal subtile neighbors.");
            Require(cell.Vertices[side]==other.Vertices[(otherSide+1)%other.Vertices.Length] &&
                cell.Vertices[(side+1)%cell.Vertices.Length]==other.Vertices[otherSide],"Boundary endpoints differ between neighbors.");
            Require((map.Vertices[edge.Start]-map.Vertices[edge.End]).sqrMagnitude>1e-12f,"Zero-length shared edge.");
            Require((cell.ParentTileId!=other.ParentTileId)==(edge.ParentBoundaryId>=0),"Invalid cross-region link.");
        }
    }
    foreach(var boundary in map.Boundaries)
    {
        Require(map.TilesById[boundary.FirstTileId].BoundaryIds.Length>0 &&
            System.Array.IndexOf(map.TilesById[boundary.FirstTileId].BoundaryIds,boundary.Id)>=0 &&
            System.Array.IndexOf(map.TilesById[boundary.SecondTileId].BoundaryIds,boundary.Id)>=0,"Missing parent boundary owner.");
        for(int i=0;i<boundary.Subedges.Length;i++)
        {
            var edge=map.Edges[boundary.Subedges[i]];
            Require(edge.ParentBoundaryId==boundary.Id &&
                (edge.Start==boundary.Vertices[i] && edge.End==boundary.Vertices[i+1] ||
                 edge.End==boundary.Vertices[i] && edge.Start==boundary.Vertices[i+1]),"A shared boundary has a gap or mismatched split.");
            int a=map.Subtiles[edge.FirstSubtile].ParentTileId,b=map.Subtiles[edge.SecondSubtile].ParentTileId;
            Require(a==boundary.FirstTileId && b==boundary.SecondTileId || b==boundary.FirstTileId && a==boundary.SecondTileId,
                "Subtile boundary connects the wrong regions.");
            crossRegion++;
        }
    }
    foreach(var tile in source.tiles)
    {
        var neighbors=new System.Collections.Generic.HashSet<int>();
        foreach(int id in map.TilesById[tile.id].BoundaryIds)
        {var edge=map.Boundaries[id];neighbors.Add(edge.FirstTileId==tile.id?edge.SecondTileId:edge.FirstTileId);}
        Require(neighbors.SetEquals(tile.neighbors),"Parent adjacency differs from the source.");
    }
    var seen=new bool[map.Subtiles.Count];var queue=new System.Collections.Generic.Queue<int>();seen[0]=true;queue.Enqueue(0);int connected=0;
    while(queue.Count>0)
    {
        var cell=map.Subtiles[queue.Dequeue()];connected++;
        foreach(int neighbor in cell.Neighbors)if(!seen[neighbor]){seen[neighbor]=true;queue.Enqueue(neighbor);}
    }
    Require(connected==map.Subtiles.Count,"Operational navigation graph is disconnected.");
    return new{parents=map.Tiles.Count,subtiles=map.Subtiles.Count,vertices=map.Vertices.Count,edges=map.Edges.Count,
        crossRegionEdges=crossRegion,pentagons,worstRelativeAreaError=worstAreaError,worstSurfaceAreaRatio,euler=2,connected};
}
ulong Fingerprint(SphericalCivilization.World.OperationalWorld map)
{
    ulong hash=14695981039346656037ul;
    void Mix(int value){unchecked{hash^=(uint)value;hash*=1099511628211ul;}}
    foreach(var p in map.Vertices){Mix(p.x.GetHashCode());Mix(p.y.GetHashCode());Mix(p.z.GetHashCode());}
    foreach(var c in map.Subtiles){Mix((int)(c.Id>>32));Mix((int)c.Id);foreach(int v in c.Vertices)Mix(v);foreach(int n in c.Neighbors)Mix(n);}
    return hash;
}
var watch=System.Diagnostics.Stopwatch.StartNew();
var main=Validate(world,globe.HexagonSubtileCount,globe.PentagonSubtileCount);
Require(globe.TriangleCount==world.Edges.Count*2,"Surface fan triangles do not cover all operational edges.");
Require(globe.GetComponentsInChildren<UnityEngine.Renderer>().Length==1,"Subtiles created individual scene renderers.");
var positions=globe.GetComponent<UnityEngine.MeshFilter>().sharedMesh.vertices;
var triangles=globe.GetComponent<UnityEngine.MeshFilter>().sharedMesh.triangles;
for(int i=0;i<triangles.Length;i+=3)
{
    var a=positions[triangles[i]];var b=positions[triangles[i+1]];var c=positions[triangles[i+2]];
    Require(UnityEngine.Vector3.Dot(UnityEngine.Vector3.Cross(b-a,c-a),a)>1e-13f,"A surface triangle is collapsed or points inward.");
}
UnityEngine.Physics.SyncTransforms();
foreach(var cell in world.Subtiles)
{
    // Probe the open interior of a fan triangle, avoiding PhysX's edge/vertex
    // tie precision when a ray goes exactly through the shared fan center.
    var point=(cell.Center+world.Vertices[cell.Vertices[0]]+world.Vertices[cell.Vertices[1]])/3f;
    var origin=globe.transform.TransformPoint(point*2f);var direction=globe.transform.TransformDirection(-point.normalized);
    Require(globe.TryGetSubtile(new UnityEngine.Ray(origin,direction),out var picked) && picked.Id==cell.Id,"Picking returned the wrong subtile: "+cell.Id);
}
var reverse=new SphericalCivilization.ReferenceWorld{schemaVersion=source.schemaVersion,tiles=(SphericalCivilization.ReferenceTile[])source.tiles.Clone()};
System.Array.Reverse(reverse.tiles);
var regenerated=SphericalCivilization.World.OperationalSubdivision.Build(reverse,new SphericalCivilization.World.SubdivisionOptions{SubtilesPerTile=globe.HexagonSubtileCount,PentagonSubtilesPerTile=globe.PentagonSubtileCount,Seed=globe.subdivisionSeed});
Require(Fingerprint(world)==Fingerprint(regenerated),"Generation depends on parent enumeration order.");
var variants=new System.Collections.Generic.List<object>();
foreach(int count in new[]{12,24,64,128})
    variants.Add(Validate(SphericalCivilization.World.OperationalSubdivision.Build(source,new SphericalCivilization.World.SubdivisionOptions{SubtilesPerTile=count}),count));
var changed=SphericalCivilization.World.OperationalSubdivision.Build(source,new SphericalCivilization.World.SubdivisionOptions{Seed=42,SubtilesPerTile=globe.HexagonSubtileCount,PentagonSubtilesPerTile=globe.PentagonSubtileCount});
Validate(changed,globe.HexagonSubtileCount,globe.PentagonSubtileCount);
Require(Fingerprint(changed)!=Fingerprint(world),"World seed did not change the interior layout.");
for(int i=0;i<world.Boundaries.Count;i++)
    Require(System.Linq.Enumerable.SequenceEqual(world.Boundaries[i].Vertices,changed.Boundaries[i].Vertices),"World seed changed a canonical parent boundary.");
var mixedCounts=new System.Collections.Generic.List<object>();
foreach(var pair in new[]{(hex:128,pent:12),(hex:12,pent:128),(hex:37,pent:24)})
{
    var map=SphericalCivilization.World.OperationalSubdivision.Build(source,new SphericalCivilization.World.SubdivisionOptions{SubtilesPerTile=pair.hex,PentagonSubtilesPerTile=pair.pent});
    mixedCounts.Add(Validate(map,pair.hex,pair.pent));
    int[] ids={map.Tiles.Find(t=>t.Corners.Length==6).Id,map.Tiles.Find(t=>t.Corners.Length==5).Id};
    var preview=SphericalCivilization.World.OperationalSubdivision.BuildPreview(source,ids,new SphericalCivilization.World.SubdivisionOptions{SubtilesPerTile=pair.hex,PentagonSubtilesPerTile=pair.pent});
    Require(preview.Subtiles.Count==pair.hex+pair.pent,"Preview generated unrelated cell interiors.");
    foreach(var cell in preview.Subtiles)
    {
        var full=map.Subtiles[map.SubtileIndicesById[cell.Id]];
        Require(cell.Vertices.Length==full.Vertices.Length && (cell.Center-full.Center).sqrMagnitude<1e-12f,"Preview and globe geometry differ.");
        for(int i=0;i<cell.Vertices.Length;i++)Require((preview.Vertices[cell.Vertices[i]]-map.Vertices[full.Vertices[i]]).sqrMagnitude<1e-12f,"Preview vertices differ from the globe.");
    }
}
return new{result="PASS",main,allSubtilesPicked=world.Subtiles.Count,reversedOrderStable=true,changedSeedPreservesBoundaries=true,
    alternateDensities=variants,mixedCounts,previewMatchesGlobe=true,milliseconds=watch.ElapsedMilliseconds};
