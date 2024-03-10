import random
import math
from deap import base, creator, tools
from shapely.geometry import Polygon, box
from shapely.affinity import rotate, scale, translate
import geopandas as gpd


def extract_geo_from_shp(shapefile_path):
    # Read shapefile
    gdf = gpd.read_file(shapefile_path)
    
    # Get a list of the geometries
    geom_list = gdf['geometry'].tolist()
    
    return geom_list

def write_rectangles_to_shp(gdf_rectangles):

    # Convert list of rectangle Polygons to GeoDataFrame and save
    #gdf_rectangles = gpd.GeoDataFrame(geometry=rectangles)
    gdf_rectangles.to_file(r"OUTPUT_PATH.shp")


MIN_WIDTH, MAX_WIDTH = 0.0001, 5
MIN_HEIGHT, MAX_HEIGHT = 0.0001, 5
MIN_ANGLE, MAX_ANGLE = 0, 90  # rotation angle range in degrees

creator.create("FitnessMax", base.Fitness, weights=(1.0,))

creator.create("Individual", list, fitness=creator.FitnessMax)

def generate_individual(polygon):
    # Generate a rectangle completely contained within the given polygon
    minx, miny, maxx, maxy = polygon.bounds
    center_x = random.uniform(minx, maxx)
    center_y = random.uniform(miny, maxy)
    width = random.uniform(MIN_WIDTH, maxx-minx)
    height = random.uniform(MIN_HEIGHT, maxy-miny)
    angle = random.uniform(MIN_ANGLE, MAX_ANGLE) # random rotation angle
    return creator.Individual([center_x, center_y, width, height, angle])

def evaluate(individual, polygon):
    # This function evaluates the "fitness" of an individual (a potential solution)
    center_x, center_y, width, height, angle = individual
    rectangle = rotate(box(center_x-width/2, center_y-height/2, center_x+width/2, center_y+height/2), angle) # creating rotated rectangle
    if not polygon.contains(rectangle):
        return (-1e20,)  # large negative penalty if rectangle is not completely within the polygon
    return (width*height,)

def find_largest_rectangle_ea(polygon, pop_size=2000, num_generations=200):
    toolbox = base.Toolbox()

    # Register function to generate a new individual
    toolbox.register("create_individual", generate_individual, polygon)
    
    # Register function to generate a new population
    toolbox.register("population", tools.initRepeat, list, toolbox.create_individual)
    
    # Register function to evaluate an individual
    toolbox.register("evaluate", evaluate, polygon=polygon)

    # Register genetic operators
    toolbox.register("mate", tools.cxTwoPoint)
    toolbox.register("mutate", tools.mutGaussian, mu=0, sigma=10, indpb=0.2)
    toolbox.register("select", tools.selTournament, tournsize=3)

    # Create initial population
    pop = toolbox.population(n=pop_size)

    # Begin the evolution
    for g in range(num_generations):
        # Select the next generation individuals
        offspring = toolbox.select(pop, k=len(pop))
        # Clone the selected individuals to safeguard against aliasing
        offspring = list(map(toolbox.clone, offspring))
        
        # Apply crossover and mutation on the offspring
        for child1, child2 in zip(offspring[::2], offspring[1::2]):
            if random.random() < 0.5:  # crossover probability
                toolbox.mate(child1, child2)
                del child1.fitness.values
                del child2.fitness.values
 
        for mutant in offspring:
            if random.random() < 0.2:  # mutation probability
                toolbox.mutate(mutant)
                del mutant.fitness.values

        # Evaluate the individuals with invalid fitness
        invalids = [ind for ind in offspring if not ind.fitness.valid]
        fitnesses = toolbox.map(toolbox.evaluate, invalids)
        for ind, fit in zip(invalids, fitnesses):
            ind.fitness.values = fit
        
        # The population is replaced by the offspring
        pop[:] = offspring
    
    # Sort individuals in descending order based on their fitness
    pop.sort(key=lambda ind: ind.fitness.values[0], reverse=True)
    
    # Return a rectangle Polygon object for the best individual
    best_ind = pop[0]
    center_x, center_y, width, height, angle = best_ind
    rectangle = rotate(box(center_x-width/2, center_y-height/2, center_x+width/2, center_y+height/2), angle)

    return rectangle

def calculate_and_save_rectangles(geometry_list):
    # List to store resulting rectangles
    rectangles = []

    # Loop over geometries
    for geom in geometry_list:
        print(f"Processing geometry {geometry_list.index(geom)+1} out of {len(geometry_list)}")
        
        # Routine to skip any invalid geometries and continue
        if not geom.is_valid:
            print("Invalid geometry, skipping...")
            continue

        # Calculate largest transcribed rectangle
        try:
            rectangle = find_largest_rectangle_ea(geom)
            rectangles.append(rectangle)
        except Exception as ex:
            print(f"Failed to calculate rectangle for geometry due to: {str(ex)}")
      
    # Convert list of rectangle Polygons to a GeoSeries
    rectangles_gs = gpd.GeoSeries(rectangles)

    # Create a new GeoDataFrame
    rectangles_gdf = gpd.GeoDataFrame(geometry=rectangles_gs)
    
    return rectangles_gdf

def inflate_rectangle_list(rect_list, polygon_list, step=0.01):
    """
    Inflates a list of rectangles to their maximum size possible inside their respective polygons.
    
    Parameters:
    rect_list : list of shapely.geometry.Polygon
        List of rectangles to be inflated.
    polygon_list : list of shapely.geometry.Polygon
        List of polygons in which the rectangles should fit.
    step : float
        The step size for each inflation operation.

    Returns:
    inflated_rects : list of shapely.geometry.Polygon
        The list of inflated rectangles.
    """
    
    inflated_rects = []
    for rect, polygon in zip(rect_list, polygon_list):
        while True:
            new_rect = scale(rect, xfact=1+step, yfact=1+step, origin='center')

            if polygon.contains(new_rect):
                rect = new_rect
            else:
                break
        
        inflated_rects.append(rect)
        
    inflated_rects = gpd.GeoSeries(inflated_rects)
    
    inflated_rects = gpd.GeoDataFrame(geometry=inflated_rects)

    return inflated_rects

file_path = r'INPUT_PATH.shp'
gdf = extract_geo_from_shp(file_path)
rectangles = calculate_and_save_rectangles(gdf[:1])
inflated_rectangles = inflate_rectangle_list(list(rectangles['geometry']), gdf[:1])
write_rectangles_to_shp(inflated_rectangles)
