// Pure geometry, adjacency, coverage and escape rules. No synthetic input or UI interaction.
var globe=UnityEngine.Object.FindFirstObjectByType<SphericalCivilization.GlobePreview>();
var world=globe.Topology;
void Require(bool value,string message){if(!value)throw new System.Exception(message);}
var rectangle=new[]{new UnityEngine.Vector2(-3,-1),new UnityEngine.Vector2(-1,-1),new UnityEngine.Vector2(0,0),
    new UnityEngine.Vector2(-3,1),new UnityEngine.Vector2(3,-1),new UnityEngine.Vector2(3,1),new UnityEngine.Vector2(1,1),new UnityEngine.Vector2(-3,-1)};
var knownHull=SphericalCivilization.Battle.Battlefield.ConvexHull(rectangle);
Require(knownHull.Length==4 && System.Math.Abs(SphericalCivilization.Battle.Battlefield.SignedArea(knownHull)-12)<.00001,"Rubber-band hull failed with duplicate, collinear and interior vertices.");
System.Array.Reverse(rectangle);
var reversedHull=SphericalCivilization.Battle.Battlefield.ConvexHull(rectangle);
for(int i=0;i<knownHull.Length;i++)Require(knownHull[i].Equals(reversedHull[i]),"Hull depends on input order.");
var pairs=new System.Collections.Generic.List<(int first,int second)>();
int pent=world.Tiles.Find(t=>t.Corners.Length==5).SubtileIndices[0];
pairs.Add((pent,SphericalCivilization.Battle.Battlefield.ChooseNeighbor(world,pent)));
var across=world.Edges.Find(e=>e.ParentBoundaryId>=0);
pairs.Add((across.FirstSubtile,across.SecondSubtile));
var tiny=world.Edges[0];
foreach(var e in world.Edges)if((world.Vertices[e.Start]-world.Vertices[e.End]).sqrMagnitude<(world.Vertices[tiny.Start]-world.Vertices[tiny.End]).sqrMagnitude)tiny=e;
pairs.Add((tiny.FirstSubtile,tiny.SecondSubtile));
int middle=world.Tiles.Find(t=>t.Corners.Length==6).SubtileIndices[world.Tiles.Find(t=>t.Corners.Length==6).SubtileIndices.Length/2];
pairs.Add((middle,SphericalCivilization.Battle.Battlefield.ChooseNeighbor(world,middle)));
var priorJson=UnityEditor.SessionState.GetString("BattleHull.Prior","");
if(!string.IsNullOrEmpty(priorJson))
{
    var prior=Newtonsoft.Json.Linq.JObject.Parse(priorJson);
    if(prior["first"].Type!=Newtonsoft.Json.Linq.JTokenType.Null && prior["second"].Type!=Newtonsoft.Json.Linq.JTokenType.Null)
        pairs.Add((world.SubtileIndicesById[(long)prior["first"]],world.SubtileIndicesById[(long)prior["second"]]));
}
var reports=new System.Collections.Generic.List<object>();
int casesWithFilledGaps=0;
foreach(var pair in pairs)
foreach(float angle in new[]{0f,.73f,2.8f,-2.5f})
{
    var f=SphericalCivilization.Battle.Battlefield.Build(world,pair.first,pair.second,angle);
    var canonical=SphericalCivilization.Battle.Battlefield.Build(world,pair.first,pair.second,0);
    Require(canonical.Hexes.Count==f.Hexes.Count,"Camera orientation changed the geographic hex count.");
    for(int i=0;i<f.Hexes.Count;i++)Require(canonical.Hexes[i].Coord.Equals(f.Hexes[i].Coord) && canonical.Hexes[i].SourceSubtileIndex==f.Hexes[i].SourceSubtileIndex,"Camera orientation changed a tactical cell ID or its owner.");
    Require(f.CoreHexCount>0 && f.Hexes.Count>f.CoreHexCount,"No retreat band generated.");
    var hull=f.PlayableBoundary;
    Require(hull.Length>=3,"No playable hull generated.");
    for(int i=0;i<hull.Length;i++)
    {
        Require(SphericalCivilization.Battle.Battlefield.Cross(hull[(i+1)%hull.Length]-hull[i],hull[(i+2)%hull.Length]-hull[(i+1)%hull.Length])>0,"Playable boundary is not strictly convex and CCW.");
        foreach(var region in new[]{f.Regions[0],f.Regions[1]})foreach(var p in region.Polygon)
            Require(SphericalCivilization.Battle.Battlefield.Contains(hull,p),"Hull excludes a source polygon vertex.");
    }
    Require(UnityEngine.Vector3.Dot(UnityEngine.Vector3.Cross(f.AxisX,f.AxisY),f.Normal)>.999f,"Battle frame is mirrored.");
    var edge=world.Edges[f.SharedEdgeId];var delta=world.Vertices[edge.End]-world.Vertices[edge.Start];
    var direction=new UnityEngine.Vector2(UnityEngine.Vector3.Dot(delta,f.AxisX),UnityEngine.Vector3.Dot(delta,f.AxisY));
    float actual=UnityEngine.Mathf.Atan2(direction.y,direction.x)+f.ScreenAngle;
    Require(UnityEngine.Mathf.Abs(UnityEngine.Mathf.DeltaAngle(actual*UnityEngine.Mathf.Rad2Deg,angle*UnityEngine.Mathf.Rad2Deg))<.001f,"Shared boundary orientation was not preserved.");
    var distances=new int[f.Hexes.Count];System.Array.Fill(distances,-1);var queue=new System.Collections.Generic.Queue<int>();
    for(int i=0;i<f.CoreHexCount;i++){distances[i]=0;queue.Enqueue(i);}
    while(queue.Count>0){int i=queue.Dequeue();foreach(int next in f.Hexes[i].Neighbors)if(next>=0 && distances[next]<0){distances[next]=distances[i]+1;queue.Enqueue(next);}}
    var layers=new int[4];double covered=0;int filledGapCells=0,firstGap=-1;
    for(int i=0;i<f.Hexes.Count;i++)
    {
        var hex=f.Hexes[i];layers[hex.RetreatRow]++;
        bool inside=SphericalCivilization.Battle.Battlefield.Contains(hull,hex.Coord.Center);
        Require(!inside || hex.RetreatRow==0,"Interior hull cell was classified as retreat or escape.");
        if(inside && !SphericalCivilization.Battle.Battlefield.Contains(f.Regions[0].Polygon,hex.Coord.Center) && !SphericalCivilization.Battle.Battlefield.Contains(f.Regions[1].Polygon,hex.Coord.Center))
        {filledGapCells++;firstGap=i;}
        Require(distances[i]==hex.RetreatRow && hex.RetreatRow<=3,"Retreat rows are not exact graph-distance rings.");
        Require(f.IsEscapeCell(hex.Coord)==(hex.RetreatRow==3),"Wrong escape row.");
        Require(f.TryGetHex(hex.Coord.Center,out int found) && found==i,"Hex center lookup failed.");
        Require(UnityEngine.Mathf.Abs(f.OpacityAt(hex.Coord.Center)-SphericalCivilization.Battle.Battlefield.Opacity(hex.RetreatRow))<.0001f,"Incorrect fade at hex center.");
        foreach(int neighbor in hex.Neighbors)if(neighbor>=0)
        {
            Require(System.Array.IndexOf(f.Hexes[neighbor].Neighbors,i)>=0,"Nonreciprocal battle neighbors.");
            Require(UnityEngine.Mathf.Abs((hex.Coord.Center-f.Hexes[neighbor].Coord.Center).magnitude-UnityEngine.Mathf.Sqrt(3))<.0001f,"Hex grid spacing changed across a seam.");
        }
        if(hex.RetreatRow==0)covered+=hex.Coverage*2.598076211353316;
    }
    foreach(int count in layers)Require(count>0,"A retreat row is missing.");
    double sourceArea=SphericalCivilization.Battle.Battlefield.SignedArea(f.Regions[0].Polygon)+SphericalCivilization.Battle.Battlefield.SignedArea(f.Regions[1].Polygon);
    double area=SphericalCivilization.Battle.Battlefield.SignedArea(hull);
    Require(area>=sourceArea-.001,"Hull is smaller than its source polygons.");
    Require(System.Math.Abs(sourceArea-900*2.598076211353316)/sourceArea<.00001,"Hull expansion changed the original hex size.");
    Require(System.Math.Abs(covered-area)/area<.0001,"Hex coverage lost part of the convex hull.");
    // Connectedness, independently of the multi-source ring-distance traversal.
    var seen=new bool[f.Hexes.Count];queue.Enqueue(0);seen[0]=true;int connected=0;
    while(queue.Count>0){int i=queue.Dequeue();connected++;foreach(int next in f.Hexes[i].Neighbors)if(next>=0 && !seen[next]){seen[next]=true;queue.Enqueue(next);}}
    Require(connected==f.Hexes.Count,"Battle graph is disconnected.");
    var coreSeen=new bool[f.CoreHexCount];queue.Enqueue(0);coreSeen[0]=true;int coreConnected=0;
    while(queue.Count>0){int i=queue.Dequeue();coreConnected++;foreach(int next in f.Hexes[i].Neighbors)if(next>=0 && next<f.CoreHexCount && !coreSeen[next]){coreSeen[next]=true;queue.Enqueue(next);}}
    Require(coreConnected==f.CoreHexCount,"Playable hull is disconnected without retreat cells.");
    Require(f.Units.Count==2 && !f.Units[0].Escaped && !f.Units[1].Escaped,"Test unit placement failed.");
    if(firstGap>=0)
    {
        var route=f.FindPath(0,firstGap);Require(route.Count>0,"Cannot move into the added hull area.");
        foreach(int next in route)Require(f.TryMoveUnit(0,next),"Hull interior move failed.");
        Require(!f.Units[0].Escaped,"Unit escaped inside the added hull area.");
        casesWithFilledGaps++;
    }
    for(int row=1;row<=3;row++)
    {
        System.Collections.Generic.List<int> route=null;
        for(int i=0;i<f.Hexes.Count;i++)if(f.Hexes[i].RetreatRow==row)
        {var path=f.FindPath(0,i);if(path.Count>0 && (route==null || path.Count<route.Count))route=path;}
        Require(route!=null,"Cannot reach retreat row "+row);
        foreach(int next in route)Require(f.TryMoveUnit(0,next),"A valid battle move was rejected.");
        Require(f.Units[0].Escaped==(row==3),"Unit escaped too early or failed to escape on row 3.");
    }
    Require(f.UnitAt(f.Units[0].HexIndex)==-1 && !f.TryMoveUnit(0,0),"Escaped unit can still act.");
    reports.Add(new{pair.first,pair.second,angle,core=f.CoreHexCount,layers,filledGapCells,hullExpansion=area/sourceArea,contextRegions=f.Regions.Count,coverageError=System.Math.Abs(covered-area)/area});
}
Require(casesWithFilledGaps>0,"No concave pair tested the added hull area.");
return new{result="PASS",cases=reports.Count,casesWithFilledGaps,checks=reports};
