// Surface-area statistics only. No input or UI interaction.
var globe = UnityEngine.Object.FindFirstObjectByType<SphericalCivilization.GlobePreview>();
var world = globe.Topology;
double Area(SphericalCivilization.World.OperationalSubtile cell)
{
    double area=0;
    for(int i=0;i<cell.Vertices.Length;i++)
    {
        var a=world.Vertices[cell.Vertices[i]];var b=world.Vertices[cell.Vertices[(i+1)%cell.Vertices.Length]];var c=cell.Center;
        double ax=(double)a.x-c.x,ay=(double)a.y-c.y,az=(double)a.z-c.z;
        double bx=(double)b.x-c.x,by=(double)b.y-c.y,bz=(double)b.z-c.z;
        double x=ay*bz-az*by,y=az*bx-ax*bz,z=ax*by-ay*bx;
        area+=System.Math.Sqrt(x*x+y*y+z*z)*0.5;
    }
    return area;
}
double Quantile(System.Collections.Generic.List<double> sorted,double t)
{
    double index=(sorted.Count-1)*t;int a=(int)index,b=System.Math.Min(a+1,sorted.Count-1);
    return sorted[a]+(sorted[b]-sorted[a])*(index-a);
}
var areas=new System.Collections.Generic.List<double>();
var ratios=new System.Collections.Generic.List<double>();
var rows=new System.Collections.Generic.List<object>();
double total=0,sumSquares=0;int violations=0,worstParent=-1;double worstRatio=0;
foreach(var tile in world.Tiles)
{
    double min=double.MaxValue,max=0,sum=0;
    foreach(int index in tile.SubtileIndices)
    {
        double area=Area(world.Subtiles[index]);areas.Add(area);sum+=area;total+=area;sumSquares+=area*area;
        min=System.Math.Min(min,area);max=System.Math.Max(max,area);
    }
    double ratio=max/min;ratios.Add(ratio);if(ratio>1.5+1e-6)violations++;
    if(ratio>worstRatio){worstRatio=ratio;worstParent=tile.Id;}
    rows.Add(new{parent=tile.Id,count=tile.SubtileIndices.Length,minimum=min,maximum=max,mean=sum/tile.SubtileIndices.Length,ratio});
}
areas.Sort();ratios.Sort();double mean=total/areas.Count;double deviation=System.Math.Sqrt(sumSquares/areas.Count-mean*mean);
var summary=new{cells=areas.Count,parents=world.Tiles.Count,totalSurfaceArea=total,meanArea=mean,minimumArea=areas[0],maximumArea=areas[areas.Count-1],
    standardDeviation=deviation,coefficientOfVariation=deviation/mean,areaP05=Quantile(areas,.05),areaMedian=Quantile(areas,.5),areaP95=Quantile(areas,.95),
    parentRatioMedian=Quantile(ratios,.5),parentRatioP95=Quantile(ratios,.95),worstParentRatio=worstRatio,worstParent,parentsOverLimit=violations};
string directory=System.IO.Path.GetFullPath(System.IO.Path.Combine(UnityEngine.Application.dataPath,"../Library/SubtileAreaAnalysis"));
System.IO.Directory.CreateDirectory(directory);
System.IO.File.WriteAllText(System.IO.Path.Combine(directory,"current-summary.json"),Newtonsoft.Json.JsonConvert.SerializeObject(new{summary,parents=rows},Newtonsoft.Json.Formatting.Indented));
var vertexRows=new System.Collections.Generic.List<float[]>();foreach(var p in world.Vertices)vertexRows.Add(new[]{p.x,p.y,p.z});
var cellRows=new System.Collections.Generic.List<object>();foreach(var c in world.Subtiles)cellRows.Add(new{id=c.Id,parent=c.ParentTileId,vertices=c.Vertices});
var tileRows=new System.Collections.Generic.List<object>();foreach(var t in world.Tiles)tileRows.Add(new{id=t.Id,corners=t.Corners,normal=new[]{t.Normal.x,t.Normal.y,t.Normal.z}});
System.IO.File.WriteAllText(System.IO.Path.Combine(directory,"current-topology.json"),Newtonsoft.Json.JsonConvert.SerializeObject(new{vertices=vertexRows,cells=cellRows,tiles=tileRows}));
return summary;
