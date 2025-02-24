import os
import os.path as osp

import time
import argparse
import subprocess

import mmcv
import tempfile
from collections import defaultdict
from mmtrack.apis import inference_mot, init_model

import wandb

def parse_args():
    parser = argparse.ArgumentParser(description='Run mmtracking')
    parser.add_argument('-config', help='path to config file', default=None)
    parser.add_argument('-checkpoint', help='checkpoint download link', default=None)
    return parser.parse_args()

def runcmd(cmd, verbose = False, *args, **kwargs):

    process = subprocess.Popen(
        cmd,
        stdout = subprocess.PIPE,
        stderr = subprocess.PIPE,
        text = True,
        shell = True
    )
    std_out, std_err = process.communicate()
    if verbose:
        print(std_out.strip(), std_err)
    pass

def main():
    args = parse_args()

    assert args.config, "No config file"

    input_folder = "data/DNP/video/"
    output_ano = "output/DNP/anotations/"
    output_vid = "output/DNP/videos/"

#     mot_config = 'configs/mot/bytetrack/bytetrack_yolox_x_crowdhuman_mot17-private-half.py'
#     mot_checkpoint = 'checkpoints/bytetrack_yolox_x_crowdhuman_mot17-private-half_20211218_205500-1985c9f0.pth'
    mot_config = args.config
    mot_checkpoint = osp.join("checkpoints", args.checkpoint.split('/')[-1])

    # if checkpoint is not downloaded, download it
    if not osp.exists(mot_checkpoint):
        print("Downdloading checkpoint ...")
        runcmd(f"wget -c {args.checkpoint} -P ./checkpoints")
        print("Finished")
    else:
         print("Checkpoint is downloaded")

    mot_model = init_model(mot_config, mot_checkpoint, device='cuda:0')

    file = open('output/DNP/time.txt', mode='w')
    wandb.login()

    run = wandb.init(
        # Set the project where this run will be logged
        project="DNP-mmtracking",

        # Track hyperparameters and run metadata
        config={
            "algorithm": args.config.split("/")[2],
            "config": mot_config.split("/")[-1],
            "checkpoint": args.checkpoint.split('/')[-1]
    })

    print("Detect Classes:", mot_model.CLASSES)
    print()

    for input_file in sorted(os.listdir(input_folder)):
        print(f"==========={input_file}==========\n")
        file.write(f"==========={input_file}==========\n")

        input_video = osp.join(input_folder, input_file)
        input_file = input_file.split(".")[0]
        
        imgs = mmcv.VideoReader(input_video)

        # build the model from a config file
        
        prog_bar = mmcv.ProgressBar(len(imgs))
        out_dir = tempfile.TemporaryDirectory()
        out_path = out_dir.name

        pred_file = osp.join(output_ano, input_file + ".json")
        output = osp.join(output_vid, input_file + ".mp4")

        out_data = defaultdict(list)

        time_per_frame = 0
        
        start_time = time.time()
        # test and show/save the images
        for i, img in enumerate(imgs):
                start_frame = time.time()
                result = inference_mot(mot_model, img, frame_id=i)
                end_frame = time.time()
                time_per_frame += end_frame - start_frame

                out_data[i].append(result)
                mot_model.show_result(
                                img,
                                result,
                                show=False,
                                wait_time=int(1000. / imgs.fps),
                                out_file=f'{out_path}/{i:06d}.jpg')
                prog_bar.update()
        end_time = time.time()

        fps = len(imgs) / (end_time - start_time)
        file.write("Average FPS: %s seconds\n" % (fps))
        time_per_frame = time_per_frame / len(imgs)
        file.write("Time per Frame: %s seconds \n" % (time_per_frame))

        # print out pred in json format
        start_time = time.time()
        mmcv.dump(out_data, pred_file)
        end_time = time.time()

        json_time = end_time - start_time
        file.write("Create json anotations: %s seconds\n" % (json_time))
        
        print(f'\nMaking the output video at {output} with a FPS of {imgs.fps}\n')
        start_time = time.time()
        mmcv.frames2video(out_path, output, fps=imgs.fps, fourcc='mp4v')
        end_time = time.time()

        video_time = end_time - start_time
        file.write("Create output video: %s seconds\n" % (video_time))

        out_dir.cleanup()

        file.write('\n')
        print()

        wandb.log({
            "Average FPS": fps,
            "Time per Frame": time_per_frame,
            "Create json anotations": json_time,
            "Create output video": video_time
        })
        
    file.close()

if __name__ == "__main__":
     main()